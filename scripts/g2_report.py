# -*- coding: utf-8 -*-
"""Kayıtlı bir G-2 matris JSON'undan raporu yeniden render eder (GPU gerekmez).

Matris koşusu (run_g2_matrix.py) hem JSON hem raporu yazar; bu script rapor
şablonu değişince ya da eski bir sonuçtan rapor gerektiğinde modelleri yeniden
koşmadan g2-report.md üretir.

Çalıştırma:
  python scripts/g2_report.py                       # en yeni *_g2_matrix.json
  python scripts/g2_report.py eval/results/X.json   # belirli dosya
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_g2_matrix import render_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    results_dir = ROOT / "eval" / "results"
    if len(sys.argv) > 1:
        # Göreli yol verilebilsin: relative_to() mutlak/göreli karışımında patlıyor.
        src = Path(sys.argv[1]).resolve()
    else:
        candidates = sorted(results_dir.glob("*_g2_matrix.json"))
        if not candidates:
            print("Matris JSON bulunamadı (eval/results/*_g2_matrix.json). Önce run_g2_matrix.py.")
            return 1
        src = candidates[-1]

    matrix = json.loads(src.read_text(encoding="utf-8"))
    out = results_dir / "g2-report.md"
    out.write_text(render_report(matrix), encoding="utf-8")
    print(f"Kaynak: {src.relative_to(ROOT)}")
    print(f"Rapor : {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
