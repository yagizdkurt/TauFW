#!/usr/bin/env bash

J_VALUES=("VTight") #"VVLoose" "VLoose" "Loose" "Medium" "Tight")
E_VALUES=("Tight") #"VVLoose")

YEAR=2025
CONFIG="TauES_ID/config/config_coarse_TT.yml"
CONFIG_MM="TauES/config/FitSetup_mumu.yml" #CR config

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M")
LOGFILE="run_TES_${TIMESTAMP}.log"

echo "Logging to ${LOGFILE}"
echo "Run started at $(date)" | tee -a "$LOGFILE"

for j in "${J_VALUES[@]}"; do
    for e in "${E_VALUES[@]}"; do
        
        {
            echo "------------------------------------------------------------"
            echo "Running: -j ${j}, -e ${e}"
            echo "------------------------------------------------------------"
        } | tee -a "$LOGFILE"

        python3 TauES/createinputsTES.py \
            -y ${YEAR} \
            -c ${CONFIG} \
            -j ${j} \
            -e ${e} 2>&1 | tee -a "$LOGFILE"
        STATUS=${PIPESTATUS[0]}   # BUGS F03: status of the mutau command (it was read after the mumu command)
        python3 TauES/createinputsTES.py \
            -y ${YEAR} \
            -c ${CONFIG_MM} \
            -j ${j} \
            -e ${e}
        STATUS_MM=$?
        [[ $STATUS -eq 0 ]] && STATUS=$STATUS_MM   # BUGS F03: a mumu failure counts too

        if [[ $STATUS -ne 0 ]]; then
            echo "❌ ERROR: iteration failed for j=${j}, e=${e} (exit code $STATUS)" | tee -a "$LOGFILE"
            echo "→ Skipping and continuing..." | tee -a "$LOGFILE"
            continue
        fi

        echo "✔ Completed j=${j}, e=${e}" | tee -a "$LOGFILE"
        echo | tee -a "$LOGFILE"

    done
done

echo "Run finished at $(date)" | tee -a "$LOGFILE"
