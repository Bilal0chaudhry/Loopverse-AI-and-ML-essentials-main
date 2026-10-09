# AI Error Log

## Entry 1 (Sprint 2)
- **Context + wrong output:** Asked the AI to generate answers using the retrieved documents, but the AI sometimes cited document IDs that it hadn't actually retrieved for that specific question, or hallucinated citations for general knowledge.
- **Risk:** This breaks the core rule of RAG: answers must be grounded *only* in explicitly retrieved context. Hallucinated citations destroy trust.
- **Detection:** Discovered during manual testing when the assistant cited `DOC-02` (a superseded document) despite the retriever blocking it, because the AI guessed the ID from its training data.
- **Correction + verification:** `_finish()` in `assistant.py` now removes any citation whose document was not retrieved for that question, and `sources` is built only from citations left in the answer. `tests/test_assistant.py` checks that every source appears as a citation in the answer text.

## Entry 2 (Sprint 1)
- **Context + wrong output:** Asked the AI to handle missing dates in the sensor data by simply taking the 7-day average. The AI implemented an interpolation strategy that leaked future data into past missing values during validation.
- **Risk:** This causes a massive data leak (time-travel). The model would score unrealistically well in walk-forward validation because it was effectively "seeing" future pollution levels to fill the gaps.
- **Detection:** We noticed our validation MAE dropped suspiciously low (under 10). A manual code review showed `interpolate(limit_direction="both")` being applied across the entire timeline *before* the chronological split.
- **Correction + verification:** We restricted interpolation to only the training periods inside the walk-forward loops, ensuring future data is never used to fill past gaps. The MAE stabilized at a realistic ~13.4.

## Entry 3 (Sprint 1)
- **Context + wrong output:** Asked the AI to merge the two sensor files. It joined them directly on `timestamp`, treating batch_1 UTC times and batch_2 Pakistan dates as the same clock and AQI as PM2.5.
- **Risk:** Every batch_1 reading would land on the wrong day and AQI values would be mixed with PM2.5, corrupting all training data and forecasts.
- **Detection:** `src/audit_crosscheck.py` compared the same sensor-days across both files: without the +5h shift the files differed by about 20.6 µg/m³ on average, and without AQI conversion by about 74.3.
- **Correction + verification:** Added the +5h shift and the inverse EPA AQI formula in `data_pipeline.py`, plus an assert that over 99% of rows agree after conversion. The measured gap dropped to 0.44 µg/m³ (AQI rounding only), and the assert runs on every rebuild.
