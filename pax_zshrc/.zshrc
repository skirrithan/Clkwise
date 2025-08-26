export PAXREPO=/Users/kirrithan/pax
alias pax-activate='source ${PAXREPO}/../.venv/bin/activate && cd ${PAXREPO}'
source "~/.cargo/env"

# Allow a comment and a command on the same line in an interactive session:
# https://unix.stackexchange.com/questions/557486/allowing-comments-in-interactive-zsh-commands
setopt interactive_comments

# Squash the zsh warning when using rm *
setopt rmstarsilent

# color chart:
# https://jonasjacek.github.io/colors
export PS1="%F{45}%n%F{10}%B@%b%F{113}%m%F{10}:%F{185}%~%F{10}>"

export PAXREPO=/Users/kirrithan/repos/pax-markets/pax
export PATH=~/.local/bin:${PATH}:/usr/local/go/bin:~/go/bin
export LD_LIBRARY_PATH=/home/linuxbrew/.linuxbrew/lib
export PYTHONDONTWRITEBYTECODE=1
export ZLE_REMOVE_SUFFIX_CHARS=""

alias ll='ls -lhG'
alias grep='grep --exclude-dir=.git -s --color=auto'
alias history='history 1'
alias pytest='pytest -p no:cacheprovider -p no:warnings'
alias log-pytest='pytest -p no:cacheprovider -p no:warnings --capture=tee-sys'

alias jq-fpga-images-query="jq '.FpgaImages[] | select(.Public==false)'"
alias jq-pending-images-query="jq '. | select(.State.Code == \"pending\")'"
alias ls-fpga-images='aws ec2 describe-fpga-images | jq-fpga-images-query'
alias gl="git log --pretty=format:'%h %cs %ae %s'"
alias git-lineal-number='git rev-list --count HEAD'
alias pax-activate='source ${PAXREPO}/.venv/bin/activate && cd ${PAXREPO}'
alias web-activate='source ${PAXREPO}/.web-venv/bin/activate && cd ${WEBREPO}'
alias cargo-pipe='cargo run -q 2>&1 >&-'

function ls-pending-images() {
    ls-fpga-images | jq-pending-images-query
}

autoload -Uz compinit && compinit
