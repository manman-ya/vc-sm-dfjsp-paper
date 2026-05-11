#!/usr/bin/env bash
set -euo pipefail

# Linux runner for one SDMK instance with resumable stages.
# Usage:
#   bash scripts/run_sdmk05_profiles.sh quick
#   bash scripts/run_sdmk05_profiles.sh medium
#   bash scripts/run_sdmk05_profiles.sh full
#
# Optional environment overrides:
#   INSTANCE=sdmk05 DATA_DIR=data/sdmk01-15_x2_r3r4 OUT_ROOT=reports/repro/sdmk05_medium_run bash scripts/run_sdmk05_profiles.sh medium

PROFILE="${1:-medium}"
INSTANCE="${INSTANCE:-sdmk05}"
DATA_DIR="${DATA_DIR:-data/sdmk01-15_x2_r3r4}"
PYTHON="${PYTHON:-python3}"

case "${PROFILE}" in
  quick)
    N_RUNS=2
    TIME_LIMIT_S=8
    MAX_ITER=3
    TAGUCHI_RUNS=2
    TAGUCHI_TIME_LIMIT=8
    TAGUCHI_MAX_ITER=3
    BASE_EXPERIMENT_CONFIG="configs/repro/experiment_01_15_quick.yaml"
    BASE_ABLATION_CONFIG="configs/repro/ablation_01_15_quick.yaml"
    ;;
  medium)
    N_RUNS=5
    TIME_LIMIT_S=30
    MAX_ITER=30
    TAGUCHI_RUNS=5
    TAGUCHI_TIME_LIMIT=30
    TAGUCHI_MAX_ITER=30
    BASE_EXPERIMENT_CONFIG="configs/repro/experiment_01_15.yaml"
    BASE_ABLATION_CONFIG="configs/repro/ablation_01_15.yaml"
    ;;
  full)
    N_RUNS=30
    TIME_LIMIT_S=100
    MAX_ITER=100
    TAGUCHI_RUNS=30
    TAGUCHI_TIME_LIMIT=100
    TAGUCHI_MAX_ITER=100
    BASE_EXPERIMENT_CONFIG="configs/repro/experiment_01_15.yaml"
    BASE_ABLATION_CONFIG="configs/repro/ablation_01_15.yaml"
    ;;
  *)
    echo "Unknown profile: ${PROFILE}" >&2
    echo "Use one of: quick, medium, full" >&2
    exit 2
    ;;
esac

OUT_ROOT="${OUT_ROOT:-reports/repro/${INSTANCE}_${PROFILE}_run}"
CONFIG_DIR="${OUT_ROOT}/configs"
COMPARE_DIR="${OUT_ROOT}/compare"
ABLATION_DIR="${OUT_ROOT}/ablation"
TAGUCHI_DIR="${OUT_ROOT}/taguchi"
TABLES_DIR="${OUT_ROOT}/tables"
FIGURES_DIR="${OUT_ROOT}/figures"
VALIDATION_DIR="${OUT_ROOT}/validation"
MARKER_DIR="${OUT_ROOT}/.done"

EXP_CONFIG="${CONFIG_DIR}/experiment_${INSTANCE}.yaml"
ABL_CONFIG="${CONFIG_DIR}/ablation_${INSTANCE}.yaml"

stage_bar() {
  local done="$1"
  local total="$2"
  local width=24
  local fill=$((done * width / total))
  local empty=$((width - fill))
  local filled
  local empty_part
  filled="$(printf '%*s' "${fill}" '' | tr ' ' '#')"
  empty_part="$(printf '%*s' "${empty}" '' | tr ' ' '-')"
  printf '[%s%s] %s/%s' "${filled}" "${empty_part}" "${done}" "${total}"
}

run_stage() {
  local index="$1"
  local marker="$2"
  shift 2
  echo
  echo "Stage ${index}/6 $(stage_bar "${index}" 6) ${marker}"
  if [[ -f "${MARKER_DIR}/${marker}.done" ]]; then
    echo "stage already complete, skipped: ${marker}"
    return
  fi
  "$@"
  touch "${MARKER_DIR}/${marker}.done"
}

cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "${CONFIG_DIR}" "${COMPARE_DIR}" "${ABLATION_DIR}" "${TAGUCHI_DIR}" "${TABLES_DIR}" "${FIGURES_DIR}" "${VALIDATION_DIR}" "${MARKER_DIR}"

if [[ ! -f "${DATA_DIR}/${INSTANCE}.json" ]]; then
  echo "Instance not found: ${DATA_DIR}/${INSTANCE}.json" >&2
  exit 1
fi

echo "profile=${PROFILE}"
echo "instance=${INSTANCE}"
echo "data_dir=${DATA_DIR}"
echo "out_root=${OUT_ROOT}"
echo "n_runs=${N_RUNS}, time_limit_s=${TIME_LIMIT_S}, max_iter=${MAX_ITER}"
echo "taguchi_runs=${TAGUCHI_RUNS}, taguchi_time_limit=${TAGUCHI_TIME_LIMIT}, taguchi_max_iter=${TAGUCHI_MAX_ITER}"

RUN_INSTANCE="${INSTANCE}" \
RUN_N_RUNS="${N_RUNS}" \
RUN_TIME_LIMIT="${TIME_LIMIT_S}" \
RUN_MAX_ITER="${MAX_ITER}" \
BASE_EXP="${BASE_EXPERIMENT_CONFIG}" \
BASE_ABL="${BASE_ABLATION_CONFIG}" \
OUT_EXP="${EXP_CONFIG}" \
OUT_ABL="${ABL_CONFIG}" \
"${PYTHON}" - <<'PY'
import os
from pathlib import Path
import yaml

instance = os.environ["RUN_INSTANCE"]
n_runs = int(os.environ["RUN_N_RUNS"])
time_limit = float(os.environ["RUN_TIME_LIMIT"])
max_iter = int(os.environ["RUN_MAX_ITER"])

def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")

exp = load(os.environ["BASE_EXP"])
abl = load(os.environ["BASE_ABL"])

for cfg in (exp, abl):
    cfg["instances"] = [instance]
    cfg["n_runs"] = n_runs
    if "eda_ts" in cfg:
        cfg["eda_ts"]["time_limit_s"] = time_limit
        cfg["eda_ts"]["max_iter"] = max_iter

for key in ("eda", "eda_vns", "nsgaii", "h_gats"):
    if key in exp:
        exp[key]["time_limit_s"] = time_limit
        exp[key]["max_iter"] = max_iter

save(os.environ["OUT_EXP"], exp)
save(os.environ["OUT_ABL"], abl)
PY

run_stage 1 validation \
  "${PYTHON}" scripts/validate_sdmk_dataset.py \
    --data-dir "${DATA_DIR}" \
    --out-dir "${VALIDATION_DIR}"

run_stage 2 compare \
  "${PYTHON}" scripts/run_experiments_repeated.py \
    --config "${EXP_CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --out-dir "${COMPARE_DIR}" \
    --resume

run_stage 3 ablation \
  "${PYTHON}" scripts/run_ablation_repeated.py \
    --config "${ABL_CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --out-dir "${ABLATION_DIR}" \
    --resume

run_stage 4 taguchi \
  "${PYTHON}" scripts/tune_params_taguchi.py \
    --instance "${INSTANCE}" \
    --data-dir "${DATA_DIR}" \
    --runs-per-combo "${TAGUCHI_RUNS}" \
    --time-limit "${TAGUCHI_TIME_LIMIT}" \
    --max-iter "${TAGUCHI_MAX_ITER}" \
    --out-dir "${TAGUCHI_DIR}" \
    --resume

run_stage 5 tables \
  "${PYTHON}" scripts/build_paper_tables.py \
    --compare-dir "${COMPARE_DIR}" \
    --ablation-dir "${ABLATION_DIR}" \
    --out-dir "${TABLES_DIR}"

run_stage 6 figures \
  "${PYTHON}" scripts/visualize_repro_results.py \
    --compare-dir "${COMPARE_DIR}" \
    --config "${EXP_CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --out-dir "${FIGURES_DIR}" \
    --gantt-instance "${INSTANCE}" \
    --gantt-algorithm "EDA-TS" \
    --gantt-run 1

find "${OUT_ROOT}" -type f | sort > "${OUT_ROOT}/artifact_manifest.txt"
echo
echo "done: ${OUT_ROOT}"
