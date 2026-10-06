#!/usr/bin/env bash
set -euo pipefail

# YDB Skills Installer
# Installs YDB skills (ydb-core, ydb-table, ydb-search, ydb-docs) for
# AI coding agents. Supports: Claude Code, Cursor, Windsurf, GitHub Copilot,
# Codex CLI, Roo Code, Gemini CLI, Amp, Kiro, Trae, and generic .agents/.

REPO_URL="https://github.com/ydb-platform/ydb-ai-skills"
VERSION="0.3.0"

# ── Skills list ─────────────────────────────────────────────────────────────

SKILLS=(ydb-core ydb-table ydb-search ydb-docs)

# ydb-core is the baseline onboarding/router skill. Any surface skill selection
# auto-includes ydb-core unless --no-core is passed — other skills deep-link
# into its anchor sections (`../ydb-core/SKILL.md#<anchor>`).
DEFAULT_CO_SKILL="ydb-core"

# ── Agent definitions ───────────────────────────────────────────────────────
# Format: agent_name:project_dir:global_dir
# project_dir is relative to project root, global_dir is absolute

AGENTS=(
  "claude:.claude/skills:${HOME}/.claude/skills"
  "cursor:.cursor/skills:"
  "windsurf:.windsurf/skills:"
  "copilot:.github/skills:${HOME}/.copilot/skills"
  "codex:.agents/skills:${HOME}/.codex/skills"
  "roo:.roo/skills:"
  "gemini:.gemini/skills:${HOME}/.gemini/skills"
  "amp:.agents/skills:${HOME}/.config/agents/skills"
  "kiro:.kiro/skills:"
  "trae:.trae/skills:"
  "generic:.agents/skills:${HOME}/.agents/skills"
)

# ── Usage ───────────────────────────────────────────────────────────────────

usage() {
  cat <<EOF
YDB Skills Installer v${VERSION}

Usage:
  $(basename "$0") [options]

Options:
  --agent=NAME[,NAME]   Install for specific agent(s). Comma-separated.
                         Agents: claude, cursor, windsurf, copilot, codex,
                                 roo, gemini, amp, kiro, trae, generic
  --all                 Install for all supported agents
  --detect              Auto-detect agents from existing config dirs
  --global              Install to user-level (global) directories
  --project=PATH        Install to project at PATH (default: current dir)
  --link                Use symlinks instead of copying (default if source is local)
  --copy                Always copy files (default for remote install)
  --skills=LIST         Install specific skills only (default: all)
                         Skills: ydb-core, ydb-table, ydb-search, ydb-docs
  --no-core             Skip auto-inclusion of ydb-core when --skills is set
                         (only respected when --skills does not already list it)
  --list                Show supported agents and exit
  --dry-run             Show what would be done without doing it
  --uninstall           Remove installed skills
  -h, --help            Show this help

Examples:
  # Auto-detect agents and install to current project
  $(basename "$0") --detect

  # Install for Claude Code and Cursor
  $(basename "$0") --agent=claude,cursor

  # Install globally for Claude Code
  $(basename "$0") --agent=claude --global

  # Install only ydb-table (ydb-core will be auto-included)
  $(basename "$0") --all --skills=ydb-table

  # Install only ydb-table without ydb-core
  $(basename "$0") --all --skills=ydb-table --no-core

  # Remote install (auto-detect agents)
  curl -fsSL https://ai.ydb.sh | sh

  # Remote install with specific agent
  curl -fsSL https://ai.ydb.sh | sh -s -- --agent=claude

EOF
}

# ── Helpers ─────────────────────────────────────────────────────────────────

log_info()  { echo "info: $*"; }
log_ok()    { echo "ok: $*"; }
log_warn()  { echo "warn: $*"; }
log_err()   { echo "error: $*" >&2; }

get_agent_field() {
  local agent="$1" field="$2"
  for entry in "${AGENTS[@]}"; do
    IFS=':' read -r name proj glob <<< "$entry"
    if [[ "$name" == "$agent" ]]; then
      case "$field" in
        name)    echo "$name" ;;
        project) echo "$proj" ;;
        global)  echo "$glob" ;;
      esac
      return 0
    fi
  done
  return 1
}

agent_exists() {
  local agent="$1"
  for entry in "${AGENTS[@]}"; do
    IFS=':' read -r name _ _ <<< "$entry"
    [[ "$name" == "$agent" ]] && return 0
  done
  return 1
}

detect_agents() {
  local project_dir="$1"
  local detected=()

  # Check for agent config directories in project
  [[ -d "${project_dir}/.claude" ]]   && detected+=(claude)
  [[ -d "${project_dir}/.cursor" ]]   && detected+=(cursor)
  [[ -d "${project_dir}/.windsurf" ]] && detected+=(windsurf)
  [[ -d "${project_dir}/.github" ]]   && detected+=(copilot)
  [[ -d "${project_dir}/.roo" ]]      && detected+=(roo)
  [[ -d "${project_dir}/.gemini" ]]   && detected+=(gemini)
  [[ -d "${project_dir}/.amp" ]]      && detected+=(amp)
  [[ -d "${project_dir}/.kiro" ]]     && detected+=(kiro)
  [[ -d "${project_dir}/.trae" ]]     && detected+=(trae)
  [[ -d "${project_dir}/.agents" ]]   && detected+=(generic)

  # Also check for common rule files
  [[ -f "${project_dir}/.cursorrules" ]] && [[ ! " ${detected[*]} " =~ " cursor " ]] && detected+=(cursor)
  [[ -f "${project_dir}/.windsurfrules" ]] && [[ ! " ${detected[*]} " =~ " windsurf " ]] && detected+=(windsurf)
  [[ -f "${project_dir}/CLAUDE.md" ]] && [[ ! " ${detected[*]} " =~ " claude " ]] && detected+=(claude)
  [[ -f "${project_dir}/AGENTS.md" ]] && [[ ! " ${detected[*]} " =~ " codex " ]] && detected+=(codex)
  [[ -f "${project_dir}/GEMINI.md" ]] && [[ ! " ${detected[*]} " =~ " gemini " ]] && detected+=(gemini)

  # Check global dirs for global installs
  [[ -d "${HOME}/.claude" ]]          && [[ ! " ${detected[*]} " =~ " claude " ]] && detected+=(claude)
  [[ -d "${HOME}/.codex" ]]           && [[ ! " ${detected[*]} " =~ " codex " ]] && detected+=(codex)
  [[ -d "${HOME}/.gemini" ]]          && [[ ! " ${detected[*]} " =~ " gemini " ]] && detected+=(gemini)

  if [[ ${#detected[@]} -eq 0 ]]; then
    log_warn "No agents detected. Use --agent=NAME or --all to specify targets."
    log_warn "Falling back to generic (.agents/skills/)"
    detected+=(generic)
  fi

  echo "${detected[@]}"
}

# ── Source resolution ───────────────────────────────────────────────────────

resolve_source() {
  # Determine where the skill source files are
  local script_dir=""

  # BASH_SOURCE may be empty when piped (curl | sh)
  if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]:-}" != "bash" ]]; then
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi

  # Check if running from the repo (local install)
  if [[ -n "$script_dir" && -f "${script_dir}/skills/ydb-core/SKILL.md" ]]; then
    echo "local:${script_dir}"
    return 0
  fi

  # Otherwise, need to clone/download
  echo "remote:${REPO_URL}"
}

download_skills() {
  local tmp_dir
  tmp_dir=$(mktemp -d)
  log_info "Downloading YDB skills from ${REPO_URL}..."

  if command -v git &>/dev/null; then
    git clone --depth 1 --quiet "${REPO_URL}.git" "${tmp_dir}/repo" 2>/dev/null
    echo "${tmp_dir}/repo"
  elif command -v curl &>/dev/null; then
    curl -fsSL "${REPO_URL}/archive/refs/heads/main.tar.gz" | tar -xz -C "${tmp_dir}"
    echo "${tmp_dir}/skills-main"
  elif command -v wget &>/dev/null; then
    wget -qO- "${REPO_URL}/archive/refs/heads/main.tar.gz" | tar -xz -C "${tmp_dir}"
    echo "${tmp_dir}/skills-main"
  else
    log_err "git, curl, or wget required for remote install"
    exit 1
  fi
}

# ── Install logic ───────────────────────────────────────────────────────────

install_skill() {
  local skill="$1"
  local source_dir="$2"
  local target_dir="$3"
  local method="$4"  # link or copy
  local dry_run="$5"

  local skill_source="${source_dir}/skills/${skill}"
  local skill_target="${target_dir}/${skill}"

  if [[ ! -d "$skill_source" ]]; then
    log_err "Skill source not found: ${skill_source}"
    return 1
  fi

  if [[ ! -f "${skill_source}/SKILL.md" ]]; then
    log_err "Invalid skill (no SKILL.md): ${skill_source}"
    return 1
  fi

  if [[ "$dry_run" == "true" ]]; then
    if [[ "$method" == "link" ]]; then
      echo "  symlink ${skill_target} -> ${skill_source}"
    else
      echo "  copy ${skill_source} -> ${skill_target}"
    fi
    return 0
  fi

  mkdir -p "$(dirname "$skill_target")"

  # Remove existing if present
  if [[ -e "$skill_target" || -L "$skill_target" ]]; then
    rm -rf "$skill_target"
  fi

  if [[ "$method" == "link" ]]; then
    ln -s "$skill_source" "$skill_target"
  else
    cp -r "$skill_source" "$skill_target"
  fi
}

uninstall_skill() {
  local skill="$1"
  local target_dir="$2"
  local dry_run="$3"

  local skill_target="${target_dir}/${skill}"

  if [[ -e "$skill_target" || -L "$skill_target" ]]; then
    if [[ "$dry_run" == "true" ]]; then
      echo "  remove ${skill_target}"
    else
      rm -rf "$skill_target"
      log_ok "Removed ${skill_target}"
    fi
  fi
}

# ── Main ────────────────────────────────────────────────────────────────────

main() {
  local target_agents=()
  local install_skills=("${SKILLS[@]}")
  local project_dir="."
  local use_global=false
  local method=""  # auto-detect
  local dry_run=false
  local do_uninstall=false
  local do_detect=false
  local do_list=false
  local do_all=false
  local skills_explicit=false
  local no_core=false

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent=*)
        IFS=',' read -ra target_agents <<< "${1#--agent=}"
        ;;
      --all)
        do_all=true
        ;;
      --detect)
        do_detect=true
        ;;
      --global)
        use_global=true
        ;;
      --project=*)
        project_dir="${1#--project=}"
        ;;
      --link)
        method="link"
        ;;
      --copy)
        method="copy"
        ;;
      --skills=*)
        IFS=',' read -ra install_skills <<< "${1#--skills=}"
        skills_explicit=true
        ;;
      --no-core)
        no_core=true
        ;;
      --list)
        do_list=true
        ;;
      --dry-run)
        dry_run=true
        ;;
      --uninstall)
        do_uninstall=true
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log_err "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done

  # ── List mode ───────────────────────────────────────────────────────────

  if [[ "$do_list" == true ]]; then
    echo "Supported agents:"
    echo ""
    printf "  %-12s %-25s %s\n" "AGENT" "PROJECT DIR" "GLOBAL DIR"
    printf "  %-12s %-25s %s\n" "─────" "───────────" "──────────"
    for entry in "${AGENTS[@]}"; do
      IFS=':' read -r name proj glob <<< "$entry"
      printf "  %-12s %-25s %s\n" "$name" "$proj" "${glob:-(none)}"
    done
    echo ""
    echo "Available skills: ${SKILLS[*]}"
    echo "Baseline skill (auto-included): ${DEFAULT_CO_SKILL}"
    exit 0
  fi

  # ── Resolve project path ────────────────────────────────────────────────

  project_dir="$(cd "$project_dir" && pwd)"

  # ── Determine target agents ─────────────────────────────────────────────

  if [[ "$do_all" == true ]]; then
    for entry in "${AGENTS[@]}"; do
      IFS=':' read -r name _ _ <<< "$entry"
      target_agents+=("$name")
    done
  elif [[ "$do_detect" == true ]]; then
    read -ra target_agents <<< "$(detect_agents "$project_dir")"
  fi

  if [[ ${#target_agents[@]} -eq 0 ]]; then
    # Default: auto-detect when run without arguments (e.g., curl | sh)
    read -ra target_agents <<< "$(detect_agents "$project_dir")"
  fi

  # Validate agents
  for agent in "${target_agents[@]}"; do
    if ! agent_exists "$agent"; then
      log_err "Unknown agent: ${agent}"
      log_info "Use --list to see supported agents"
      exit 1
    fi
  done

  # ── Resolve source ──────────────────────────────────────────────────────

  local source_info
  source_info=$(resolve_source)
  local source_type="${source_info%%:*}"
  local source_path="${source_info#*:}"

  if [[ "$source_type" == "remote" ]]; then
    source_path=$(download_skills)
    [[ -z "$method" ]] && method="copy"
  else
    [[ -z "$method" ]] && method="link"
  fi

  # ── Auto-include ydb-core ───────────────────────────────────────────────
  # When the user explicitly picked a subset via --skills, make sure ydb-core
  # is in the set so relative `../ydb-core/SKILL.md` refs resolve. Skip if
  # --no-core was passed. When --skills wasn't used, install_skills already
  # contains the full SKILLS list.

  if [[ "$skills_explicit" == true && "$no_core" != true ]]; then
    local has_core=false
    for s in "${install_skills[@]}"; do
      [[ "$s" == "$DEFAULT_CO_SKILL" ]] && has_core=true
    done
    if [[ "$has_core" == false ]]; then
      log_info "Including ${DEFAULT_CO_SKILL} (baseline skill; pass --no-core to skip)"
      install_skills=("$DEFAULT_CO_SKILL" "${install_skills[@]}")
    fi
  fi

  # ── Validate skills ─────────────────────────────────────────────────────

  for skill in "${install_skills[@]}"; do
    if [[ ! -d "${source_path}/skills/${skill}" ]]; then
      log_err "Skill not found: ${skill} (in ${source_path}/skills/)"
      exit 1
    fi
  done

  # Static validator: frontmatter shape, no TODO(author), language-agnostic
  # invariant on YDB-level references, link resolution, RULE-<PREFIX> in
  # registry. Cheap pre-flight before touching the user's filesystem.
  local validator="${source_path}/scripts/validate-skills.py"
  if [[ -f "$validator" ]] && command -v python3 &>/dev/null; then
    if ! ( cd "$source_path" && python3 scripts/validate-skills.py ); then
      log_err "Skill validation failed; aborting install"
      exit 1
    fi
  fi

  # ── Execute ─────────────────────────────────────────────────────────────

  local action="Installing"
  [[ "$do_uninstall" == true ]] && action="Uninstalling"
  [[ "$dry_run" == true ]] && action="${action} (dry run)"

  echo "${action} YDB skills"
  echo "  Skills:  ${install_skills[*]}"
  echo "  Agents:  ${target_agents[*]}"
  echo "  Scope:   $(if $use_global; then echo "global (user)"; else echo "project (${project_dir})"; fi)"
  echo "  Method:  ${method}"
  echo ""

  local installed_count=0
  local skipped_count=0

  for agent in "${target_agents[@]}"; do
    local target_base
    if [[ "$use_global" == true ]]; then
      target_base=$(get_agent_field "$agent" "global")
      if [[ -z "$target_base" ]]; then
        log_warn "Agent '${agent}' does not support global install, skipping"
        ((skipped_count += 1))
        continue
      fi
    else
      local rel_dir
      rel_dir=$(get_agent_field "$agent" "project")
      target_base="${project_dir}/${rel_dir}"
    fi

    echo "${agent} -> ${target_base}"

    for skill in "${install_skills[@]}"; do
      if [[ "$do_uninstall" == true ]]; then
        uninstall_skill "$skill" "$target_base" "$dry_run"
      else
        if install_skill "$skill" "$source_path" "$target_base" "$method" "$dry_run"; then
          if [[ "$dry_run" != true ]]; then
            log_ok "${skill}"
          fi
          ((installed_count += 1))
        fi
      fi
    done
    echo ""
  done

  # ── Summary ─────────────────────────────────────────────────────────────

  if [[ "$dry_run" != true ]]; then
    if [[ "$do_uninstall" == true ]]; then
      log_ok "Uninstall complete"
    else
      log_ok "Installed ${installed_count} skill(s) for ${#target_agents[@]} agent(s)"
      if [[ "$method" == "link" ]]; then
        log_info "Skills are symlinked — updates to source will be reflected automatically"
      fi
    fi
  fi
}

main "$@"
