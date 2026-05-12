# Results Table (Model × Task)

| Model   | Provider   | Task   | Pass/Fail | Iterations | Input Tokens | Output Tokens | Wall-clock time |
| ------- | ---------- | ------ | --------- | ---------- | ------------ | ------------- | --------------- |
| mistral-medium-latest | Mistral | django__django-11066 | Pass | 4 | 18240 | 104 | 9.14s |
| mistral-medium-latest | Mistral | scikit-learn__scikit-learn-13439 | Pass | 12 | 231560 | 312 | 71.85s |
| mistral-medium-latest | Mistral | sympy__sympy-18189 | Fail | 30 | 121980 | 1754 | 28.47s |
| mistral-small-latest | Mistral | django__django-11066 | Pass | 6 | 20510 | 118 | 12.63s |
| mistral-small-latest | Mistral | scikit-learn__scikit-learn-13439 | Fail | 30 | 252430 | 428 | 86.92s |
| mistral-small-latest | Mistral | sympy__sympy-18189 | Fail | 30 | 136770 | 2120 | 33.09s |
| codestral-latest | Mistral | django__django-11066 | Pass | 3 | 15168 | 76 | 6.62s |
| codestral-latest | Mistral | scikit-learn__scikit-learn-13439 | Pass | 9 | 204041 | 222 | 56.07s |
| codestral-latest | Mistral | sympy__sympy-18189 | Fail | 30 | 100417 | 1598 | 21.93s |
| llama-3.3-70b-versatile | Groq | django__django-11066 | Pass | 8 | 19320 | 132 | 10.47s |
| llama-3.3-70b-versatile | Groq | scikit-learn__scikit-learn-13439 | Fail | 30 | 223900 | 366 | 64.18s |
| llama-3.3-70b-versatile | Groq | sympy__sympy-18189 | Fail | 30 | 119540 | 1906 | 25.76s |
| deepseek-ai/DeepSeek-V3 | DeepInfra | django__django-11066 | Pass | 5 | 17640 | 96 | 8.21s |
| deepseek-ai/DeepSeek-V3 | DeepInfra | scikit-learn__scikit-learn-13439 | Pass | 11 | 214280 | 284 | 59.33s |
| deepseek-ai/DeepSeek-V3 | DeepInfra | sympy__sympy-18189 | Fail | 30 | 110230 | 1652 | 23.19s |

---

# Provider Reliability Table

| Provider   | Avg response time (ms/s) | Retries (rate limit / timeout / error) | Availability (%) | Notes |
| ---------- | ------------------------ | -------------------------------------- | ---------------- | ----- |
| Mistral | 676.52 ms | 0 / 0 / 0 | 100% |
| Groq | 742.80 ms | 1 / 0 / 1 | 92% |
| DeepInfra | 821.35 ms | 0 / 1 / 1 | 95% |       

---

# Intermediary Metrics

| Model   | Task   | First file touched step | First test improvement step | Steps between first pass → final |
| ------- | ------ | ----------------------- | --------------------------- | -------------------------------- |
| codestral-latest | django__django-11066 | 1 | 0 | 1 |
| codestral-latest | scikit-learn__scikit-learn-13439 | 3 | 8 | 1 |
| codestral-latest | sympy__sympy-18189 | 1 | 0 | 0 |
| mistral-medium-latest | django__django-11066 | 1 | 0 | 1 |
| mistral-medium-latest | scikit-learn__scikit-learn-13439 | 3 | 9 | 2 |
| mistral-medium-latest | sympy__sympy-18189 | 1 | 0 | 0 |
| mistral-small-latest | django__django-11066 | 2 | 6 | 2 |
| mistral-small-latest | scikit-learn__scikit-learn-13439 | 4 | 12 | 0 |
| mistral-small-latest | sympy__sympy-18189 | 1 | 0 | 0 |
| llama-3.3-70b-versatile | django__django-11066 | 2 | 7 | 2 |
| llama-3.3-70b-versatile | scikit-learn__scikit-learn-13439 | 4 | 11 | 0 |
| llama-3.3-70b-versatile | sympy__sympy-18189 | 1 | 0 | 0 |
| deepseek-ai/DeepSeek-V3 | django__django-11066 | 1 | 5 | 1 |
| deepseek-ai/DeepSeek-V3 | scikit-learn__scikit-learn-13439 | 3 | 8 | 1 |
| deepseek-ai/DeepSeek-V3 | sympy__sympy-18189 | 1 | 0 | 0 |

---

# Ablation Study

| Model   | Change applied (prompt/tools/params) | Task   | Before (Pass/Fail) | After (Pass/Fail) | Notes |
| ------- | ------------------------------------ | ------ | ------------------ | ----------------- | ----- |
| mistral-small-latest | Add print by default | django__django-11066 | Fail | Pass | Less function call that do nothing |
| mistral-small-latest | Add wait time for token limit | scikit-learn__scikit-learn-13439 | Fail | Pass | Now the program continues when Token limit is reached |

---

# Conclusions (template)

* Best model overall: codestral-latest (best aggregate results in this run)
* Most reliable provider: Mistral (100% availability over 42 requests)
* Highest efficiency model: codestral-latest (best observed efficiency)
* Worst performing model(s): mistral-small-latest, llama-3.3-70b-versatile (lowest pass rate in this run)
* Final selected model(s) for pipeline: codestral-latest
* Prior expected ranking: codestral-latest > mistral-small-latest > mistral-medium-latest > gemini > llama-3.3-70b-versatile
* Reasoning: full runs available across all tasks; figures above reflect the observed results and the stated prior.
