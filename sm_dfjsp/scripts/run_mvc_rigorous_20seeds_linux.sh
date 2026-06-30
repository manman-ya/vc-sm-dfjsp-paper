#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

export MPLBACKEND="${MPLBACKEND:-Agg}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_DIR="${INPUT_DIR:-data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc}"
OUT_ROOT="${OUT_ROOT:-reports/mvc_mk01_15_integrated_mechanism_equalproc_rigorous_20seeds}"
POPSIZE="${POPSIZE:-80}"
FIXED_MAX_ITER="${FIXED_MAX_ITER:-150}"
FIXED_TIME_LIMIT="${FIXED_TIME_LIMIT:-12000}"
CPU_TIME_LIMIT="${CPU_TIME_LIMIT:-600}"
FE_BUDGET="${FE_BUDGET:-12000}"
SAFETY_TIME_LIMIT="${SAFETY_TIME_LIMIT:-12000}"
UNBOUNDED_MAX_ITER="${UNBOUNDED_MAX_ITER:-1000000}"
ALGORITHMS="${ALGORITHMS:-nsgaii,moead,edats-baseline,mvc-edats}"
CROSS_MODES="${CROSS_MODES:-off,on}"
SEEDS="${SEEDS:-20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447}"

FIXED_DIR="${OUT_ROOT}/fixed_iteration"
EQUAL_TIME_DIR="${OUT_ROOT}/equal_cpu_time"
EQUAL_FE_DIR="${OUT_ROOT}/equal_evaluations"
ABLATION_DIR="${OUT_ROOT}/ablation_equal_evaluations"
ANALYSIS_DIR="${OUT_ROOT}/analysis"
STATE_DIR="${OUT_ROOT}/.pipeline_state"
mkdir -p "${STATE_DIR}"

CURRENT_STAGE="startup"
trap 'printf "\nInterrupted during %s. Re-run the same command; --resume will skip completed runs.\n" "${CURRENT_STAGE}" >&2' INT TERM

run_stage() {
    local index="$1"
    local name="$2"
    local marker="$3"
    shift 3
    CURRENT_STAGE="${name}"
    if [[ -f "${marker}" ]]; then
        printf '[%s/5] skip %s (stage marker exists)\n' "${index}" "${name}"
        return
    fi
    printf '\n[%s/5] start %s\n' "${index}" "${name}"
    "$@"
    printf '%s\n' "$(date -Is)" > "${marker}"
    printf '[%s/5] done %s\n' "${index}" "${name}"
}

run_stage 1 "fixed-iteration 20-seed comparison" "${STATE_DIR}/01_fixed_iteration.done" \
    "${PYTHON_BIN}" scripts/run_mvc_experiments.py \
    --input-dir "${INPUT_DIR}" \
    --out-dir "${FIXED_DIR}" \
    --algorithms "${ALGORITHMS}" \
    --cross-modes "${CROSS_MODES}" \
    --seeds "${SEEDS}" \
    --popsize "${POPSIZE}" \
    --max-iter "${FIXED_MAX_ITER}" \
    --time-limit "${FIXED_TIME_LIMIT}" \
    --objective-dim 2 \
    --resume

run_stage 2 "equal-CPU-time comparison" "${STATE_DIR}/02_equal_cpu_time.done" \
    "${PYTHON_BIN}" scripts/run_mvc_experiments.py \
    --input-dir "${INPUT_DIR}" \
    --out-dir "${EQUAL_TIME_DIR}" \
    --algorithms "${ALGORITHMS}" \
    --cross-modes "${CROSS_MODES}" \
    --seeds "${SEEDS}" \
    --popsize "${POPSIZE}" \
    --max-iter "${UNBOUNDED_MAX_ITER}" \
    --time-limit "${CPU_TIME_LIMIT}" \
    --time-measure cpu \
    --objective-dim 2 \
    --resume

run_stage 3 "equal-function-evaluation comparison" "${STATE_DIR}/03_equal_evaluations.done" \
    "${PYTHON_BIN}" scripts/run_mvc_experiments.py \
    --input-dir "${INPUT_DIR}" \
    --out-dir "${EQUAL_FE_DIR}" \
    --algorithms "${ALGORITHMS}" \
    --cross-modes "${CROSS_MODES}" \
    --seeds "${SEEDS}" \
    --popsize "${POPSIZE}" \
    --max-iter "${UNBOUNDED_MAX_ITER}" \
    --time-limit "${SAFETY_TIME_LIMIT}" \
    --max-evaluations "${FE_BUDGET}" \
    --objective-dim 2 \
    --resume

run_stage 4 "paired ablation under equal evaluations" "${STATE_DIR}/04_ablation.done" \
    "${PYTHON_BIN}" scripts/run_mvc_full_ablation.py \
    --input-dir "${INPUT_DIR}" \
    --out-dir "${ABLATION_DIR}" \
    --variant-set official \
    --cross-chain on \
    --seeds "${SEEDS}" \
    --popsize "${POPSIZE}" \
    --max-iter "${UNBOUNDED_MAX_ITER}" \
    --time-limit "${SAFETY_TIME_LIMIT}" \
    --max-evaluations "${FE_BUDGET}" \
    --objective-dim 2 \
    --resume

run_stage 5 "statistics, convergence, and module-runtime reports" "${STATE_DIR}/05_analysis.done" \
    "${PYTHON_BIN}" scripts/analyze_mvc_rigorous_experiments.py \
    --fixed-dir "${FIXED_DIR}" \
    --equal-time-dir "${EQUAL_TIME_DIR}" \
    --equal-fe-dir "${EQUAL_FE_DIR}" \
    --ablation-dir "${ABLATION_DIR}" \
    --out-dir "${ANALYSIS_DIR}" \
    --alpha 0.05

CURRENT_STAGE="complete"
printf '\nAll stages completed. Results: %s\n' "${OUT_ROOT}"
