#!/usr/bin/env bash
# Input-histogram generation for the HYBRID VSjet measurements (ParticleNet / UParT).
# Sibling of run_inputs.sh (DeepTau). Select the tagger with TAGGER below; everything
# else (PNet/UParT WP list, separate input tree, both years) follows from it.
# VSjet WPs are the float-score WPs (Loose..VVTight); VSe stays DeepTau (-e).

TAGGER="pnet"          # pnet | upart

case "$TAGGER" in
  pnet)  CONFIG="../Configs/Fitter/tes_id/config_coarse_PNet.yml";  OUTBASE="input_pt_less_region_pnet"  ;;
  upart) CONFIG="../Configs/Fitter/tes_id/config_coarse_UParT.yml"; OUTBASE="input_pt_less_region_upart" ;;
  *) echo "unknown TAGGER=$TAGGER (use pnet|upart)"; exit 1 ;;
esac

J_VALUES=("VVTight")  #"Loose" "Medium" "Tight" "VTight" )  # PNet/UParT VSjet WPs (raw-score)
E_VALUES=("Tight") #"VVLoose")                            # DeepTau VSe WPs (hybrid)
YEARS=("2024" "2025")
CONFIG_MM="../Configs/Fitter/tes_id/FitSetup_mumu.yml"               # Z->mumu CR (tagger-independent)

TIMESTAMP=$(date +"%Y%m%d_%H%M")
LOGFILE="run_inputs_${TAGGER}_${TIMESTAMP}.log"
echo "Logging to ${LOGFILE}  (tagger=${TAGGER}, config=${CONFIG}, outbase=${OUTBASE})"
echo "Run started at $(date)" | tee -a "$LOGFILE"

for YEAR in "${YEARS[@]}"; do
  for j in "${J_VALUES[@]}"; do
    for e in "${E_VALUES[@]}"; do
      echo "------------------------------------------------------------" | tee -a "$LOGFILE"
      echo "[${TAGGER}] year=${YEAR}  VSjet=${j}  VSe(DeepTau)=${e}"        | tee -a "$LOGFILE"
      echo "------------------------------------------------------------" | tee -a "$LOGFILE"

      python3 ../Histogrammer/shapes/TauES/createinputsTES.py -y ${YEAR} -c ${CONFIG}    -j ${j} -e ${e} -O ${OUTBASE} 2>&1 | tee -a "$LOGFILE"
      STATUS=${PIPESTATUS[0]}
      python3 ../Histogrammer/shapes/TauES/createinputsTES.py -y ${YEAR} -c ${CONFIG_MM} -j ${j} -e ${e} -O ${OUTBASE}
      STATUS_MM=$?
      [[ $STATUS -eq 0 ]] && STATUS=$STATUS_MM   # BUGS F03: a mumu failure counts too

      if [[ $STATUS -ne 0 ]]; then
        echo "❌ ERROR: ${TAGGER} year=${YEAR} j=${j} e=${e} (exit ${STATUS}) — skipping" | tee -a "$LOGFILE"
        continue
      fi
      echo "✔ Completed ${TAGGER} year=${YEAR} j=${j} e=${e}" | tee -a "$LOGFILE"
    done
  done
done

echo "Run finished at $(date)" | tee -a "$LOGFILE"
