import os
import subprocess
from pathlib import Path
from difflib import HtmlDiff
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename
import json

# --- Paths ---
ROOT = Path(__file__).parent.resolve()
BACKEND = ROOT / "backend"
DATA = BACKEND / "data"
UPLOADS = DATA / "uploads"
RPT_JSON_DIR = DATA / "rpt_json_con"
LLM_OUT_DIR = DATA / "llm_out"
FRONT_DATA_DIR = DATA / "frontend_data" / "data"

# pipeline artifacts
LLM_INPUT_JSON = RPT_JSON_DIR / "llm_json_simple.json"
LLM_OUTPUT_JSON = LLM_OUT_DIR / "cerebras_out.json"
GENERATED_SV = FRONT_DATA_DIR / "top.sv"
GENERATED_TXT = FRONT_DATA_DIR / "top.txt"

# ensure dirs
for p in [UPLOADS, RPT_JSON_DIR, LLM_OUT_DIR, FRONT_DATA_DIR]:
    p.mkdir(parents=True, exist_ok=True)

ALLOWED_RPT = {".rpt", ".txt"}
ALLOWED_SV = {".sv", ".v"}

# point Flask at your custom template/static locations
app = Flask(
    __name__,
    template_folder="frontend",           # base.html, index.html, result.html live here
    static_folder="frontend/static"       # /static/style.css lives here
)
app.secret_key = "dev"  # change in prod


def run_cmd(args, cwd=ROOT):
    """Run a command and return (ok, stdout, stderr)."""
    try:
        cp = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, check=False
        )
        return (cp.returncode == 0), cp.stdout, cp.stderr
    except Exception as e:
        return False, "", str(e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_and_process():
    rpt_file = request.files.get("rpt")
    sv_file = request.files.get("sv")
    if not rpt_file or not sv_file:
        flash("Please choose both an RPT file and an SV file.")
        return redirect(url_for("home"))

    rpt_name = secure_filename(rpt_file.filename or "")
    sv_name  = secure_filename(sv_file.filename or "")

    if Path(rpt_name).suffix.lower() not in ALLOWED_RPT:
        flash("RPT must be .rpt or .txt")
        return redirect(url_for("home"))
    if Path(sv_name).suffix.lower() not in ALLOWED_SV:
        flash("SV must be .sv or .v")
        return redirect(url_for("home"))

    # save uploads
    rpt_path = UPLOADS / rpt_name
    sv_path  = UPLOADS / sv_name
    rpt_file.save(rpt_path)
    sv_file.save(sv_path)

    # ---- STEP 1: ingest -> produce llm_json_simple.json ----
    ok1, out1, err1 = run_cmd([
        os.sys.executable,
        str(BACKEND / "app" / "ingest" / "run_pipeline.py"),
        str(rpt_path)
    ])
    step1 = {"ok": ok1, "stdout": out1, "stderr": err1}

    # ---- STEP 2: LLM integration -> cerebras_out.json ----
    ok2, out2, err2 = run_cmd([
        os.sys.executable,
        str(BACKEND / "app" / "llm_integration" / "cerebras_int_no_schema.py"),
        "--timing", str(LLM_INPUT_JSON),
        "--verilog", str(sv_path),
        "--out", str(LLM_OUTPUT_JSON)
    ])
    step2 = {"ok": ok2, "stdout": out2, "stderr": err2}

    # ---- STEP 3: Extract SV artifacts -> frontend_data/data/top.sv & top.txt ----
    ok3, out3, err3 = run_cmd([
        os.sys.executable,
        str(DATA / "frontend_data" / "scripts" / "extract_sv_artifacts.py"),
        str(LLM_OUTPUT_JSON),
        "--sv", str(GENERATED_SV),
        "--txt", str(GENERATED_TXT),
    ])
    step3 = {"ok": ok3, "stdout": out3, "stderr": err3}

    # ---- Diff (original SV vs generated SV) ----
    try:
        orig = sv_path.read_text(errors="ignore").splitlines()
        gen  = (GENERATED_SV.read_text(errors="ignore").splitlines()
                if GENERATED_SV.exists() else ["<no generated SV>"])
        diff_html = HtmlDiff(wrapcolumn=80).make_table(
            orig, gen, fromdesc=f"Original: {sv_name}", todesc="Generated: top.sv",
            context=True, numlines=3
        )
    except Exception as e:
        diff_html = f"<pre>Diff error: {e}</pre>"

    # ---- Extract fix_hints from LLM_OUTPUT_JSON ----
    fix_hints = []
    try:
        if LLM_OUTPUT_JSON.exists():
            with open(LLM_OUTPUT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Try both top-level and nested (for future-proofing)
                issues = data.get("input", {}).get("issues", [])
                if issues and isinstance(issues, list):
                    for issue in issues:
                        if "fix_hints" in issue:
                            fix_hints.extend(issue["fix_hints"])
    except Exception as e:
        fix_hints = [f"Error loading fix hints: {e}"]

    pipeline_ok = step1["ok"] and step2["ok"] and step3["ok"]

    # --- Add this block ---
    generated_sv_content = None
    if GENERATED_SV.exists():
        generated_sv_content = GENERATED_SV.read_text(encoding="utf-8", errors="ignore")

    return render_template(
        "result.html",
        pipeline_ok=pipeline_ok,
        step1=step1, step2=step2, step3=step3,
        rpt_name=rpt_name, sv_name=sv_name,
        llm_input_json=str(LLM_INPUT_JSON.relative_to(ROOT)) if LLM_INPUT_JSON.exists() else None,
        llm_output_json=str(LLM_OUTPUT_JSON.relative_to(ROOT)) if LLM_OUTPUT_JSON.exists() else None,
        generated_sv=str(GENERATED_SV.relative_to(ROOT)) if GENERATED_SV.exists() else None,
        generated_txt=str(GENERATED_TXT.relative_to(ROOT)) if GENERATED_TXT.exists() else None,
        diff_html=diff_html,
        fix_hints=fix_hints,
        generated_sv_content=generated_sv_content  # <-- pass to template
    )


@app.route("/download/<path:relpath>")
def download(relpath):
    # only allow downloads from backend/data
    target = (ROOT / relpath).resolve()
    if not str(target).startswith(str(DATA.resolve())) or not target.exists():
        return "Not Found", 404
    return send_from_directory(directory=target.parent, path=target.name, as_attachment=True)


if __name__ == "__main__":
    # Flask dev server
    app.run(host="127.0.0.1", port=5050, debug=True)