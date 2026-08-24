#!/bin/bash
set -e
MODEL="/Users/Apple/Documents/hack/models/Qwen3-1.7B-Q4_K_M.gguf"
OUT="/Users/Apple/Documents/hack/results/swahili_base_check_v2.txt"
SYS="You are an offline assistant for African agricultural market prices. Answer factually and concisely. If you do not have data for something, say so directly instead of guessing."

: > "$OUT"

run_prompt () {
  local id="$1"
  local prompt="$2"
  echo "=== $id ===" | tee -a "$OUT"
  echo "PROMPT: $prompt" | tee -a "$OUT"
  echo "---" | tee -a "$OUT"
  llama-cli -m "$MODEL" -sys "$SYS" -p "$prompt" -cnv -st \
    --chat-template-kwargs '{"enable_thinking": false}' \
    -n 200 --temp 0 --repeat-penalty 1.1 --repeat-last-n 64 --seed 42 -ngl 0 --no-display-prompt --no-warmup 2>/dev/null \
    | tee -a "$OUT"
  echo "" | tee -a "$OUT"
  echo "" | tee -a "$OUT"
}

run_prompt "1_price_lookup_maize_nairobi" "Bei ya mahindi ilikuwa ngapi katika soko la Nairobi mwezi wa Januari 2024?"
run_prompt "2_price_lookup_rice_dar" "Mchele uliuzwa kwa bei gani jijini Dar es Salaam mwaka 2023?"
run_prompt "3_trend_beans" "Je, bei ya maharagwe ilipanda au kushuka kati ya Januari 2023 na Desemba 2024?"
run_prompt "4_trend_sugar" "Bei ya sukari imebadilikaje kutoka mwaka jana hadi mwaka huu?"
run_prompt "5_cross_market_rice" "Ni soko gani lenye bei ya chini zaidi ya mchele kati ya Kampala na Kigali?"
run_prompt "6_abstain_future" "Bei ya viazi itakuwa ngapi mwezi wa Machi 2027?"
run_prompt "7_abstain_obscure" "Ulikuwa na taarifa gani kuhusu bei ya mtama katika soko la Goma, DRC, mwezi Juni 2023?"
run_prompt "8_open_fluency" "Eleza kwa ufupi kwa nini bei za vyakula barani Afrika hubadilika kulingana na msimu."

echo "Done. Full transcript at $OUT"
