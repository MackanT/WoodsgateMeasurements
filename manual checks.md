# Manual checks (things I can't verify without hardware access)

## ADS1115 config register mismatch (data_collector.py)

`webgui/woodsgate_collector/woodsgate_collector/data_collector.py` sets:

```python
ADS1115_CONFIG = 0x8483  # comment claims: Single-shot, A0, ±4.096V, 128SPS
```

Decoding `0x8483` bit-by-bit against the ADS1115 config register layout gives
something different from the comment:

| Bits  | Field     | Value in 0x8483 | Meaning                                   | Comment says          |
|-------|-----------|------------------|--------------------------------------------|------------------------|
| 15    | OS        | 1                | Start single conversion                    | matches               |
| 14-12 | MUX       | 000              | Differential AIN0 vs AIN1                  | AIN0 vs GND (should be `100`) |
| 11-9  | PGA       | 010              | ±2.048V full-scale                         | ±4.096V (should be `001`) |
| 8     | MODE      | 0                | Continuous-conversion mode                 | Single-shot (should be `1`) |
| 7-5   | DR        | 100              | 128 SPS                                    | matches               |
| 4     | COMP_MODE | 0                | Traditional comparator                     | (unused, fine)        |
| 3     | COMP_POL  | 0                | Active low                                 | (unused, fine)        |
| 2     | COMP_LAT  | 0                | Non-latching                               | (unused, fine)        |
| 1-0   | COMP_QUE  | 11               | Disable comparator                         | matches               |

If the intent really is "single-ended AIN0 vs GND, ±4.096V, single-shot" (as
the comment says and as `voltage = raw_adc * 4.096 / 32767.0` assumes), the
correct config value would be **`0xC383`**, not `0x8483`.

Why this matters:
- **PGA mismatch (±2.048V configured vs ±4.096V assumed in the math)**: if the
  real sensor voltage goes above ~2.048V (likely, since `v_max = 4.089`), the
  ADC would clip/saturate well before full scale, or the voltage conversion
  formula in code silently reads roughly 2x the true value depending on where
  it clips.
- **MUX mismatch (differential AIN0-AIN1 vs single-ended AIN0-GND)**: if AIN1
  isn't wired to GND, the reading is the *difference* between AIN0 and AIN1,
  not the absolute voltage on AIN0 — could be measuring something entirely
  different than intended.
- **MODE mismatch (continuous vs single-shot)**: probably harmless in
  practice (continuous mode just keeps converting at 128 SPS and any read
  gets the latest result), but doesn't match the "single-shot" comment/intent.

### To check when you have time
1. Confirm how AIN1 is physically wired (tied to GND, or floating/used for
   something else). If tied to GND, MUX doesn't matter much in practice but
   should still be fixed for clarity/correctness.
2. Measure the actual voltage across the sense resistor at both 4mA and 20mA
   with a multimeter and compare against what the Pi currently logs
   (`v_min`/`v_max` in `data_collector.py`) to see if there's a discrepancy
   consistent with a PGA/scale mismatch.
3. If confirmed, change `ADS1115_CONFIG = 0x8483` to `0xC383` in
   `data_collector.py` (and double check `v_min`/`v_max` calibration constants
   still make sense afterward — they were tuned against whatever the ADC was
   actually reporting, right or wrong).

## Continuing from here

Once you've verified the above, come back and ask to apply the `0xC383` fix
(or whatever value matches your actual wiring) — I did not change this myself
since it affects live calibration and I have no way to verify the physical
wiring or take a multimeter reading.
