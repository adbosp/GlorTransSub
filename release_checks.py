"""Check the actual Windows runtime, bundled OCR and offline translation models."""
import argparse
import json
from pathlib import Path
import sys
import traceback


def run_release_checks(model_root=None, report_path=None):
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    model_root = Path(model_root) if model_root else base / 'models'
    report_path = Path(report_path) if report_path else base / 'release-smoke.json'
    report = {'status': 'failed', 'checks': {}, 'frozen': bool(getattr(sys, 'frozen', False))}
    try:
        if sys.platform != 'win32':
            raise RuntimeError('Release validation must run on Windows.')
        # Keep the same DLL load order as the application.
        import torch
        import torchvision
        import numpy as np
        import cv2
        import easyocr
        from PIL import Image, ImageDraw, ImageFont
        from PyQt5 import QtWidgets
        import winreg
        import win_hotkey
        import edge_tts
        import pygame
        import boto3
        import google.auth
        from opus_mt import OpusMTEngine
        torch.set_num_threads(2)
        report['checks']['windows_imports'] = 'passed'

        boxes = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]])
        assert torchvision.ops.nms(boxes, torch.tensor([0.9, 0.8]), 0.5).tolist() == [0]
        assert cv2.cvtColor(np.zeros((4, 4, 3), dtype=np.uint8), cv2.COLOR_RGB2GRAY).shape == (4, 4)
        report['checks']['compiled_cpu_operators'] = 'passed'

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        label = QtWidgets.QLabel('GloSub Windows release check')
        label.show()
        app.processEvents()
        assert label.text() == 'GloSub Windows release check'
        label.close()
        report['checks']['qt_widget'] = 'passed'

        reader = easyocr.Reader(
            ['en'], gpu=False, verbose=False, download_enabled=False,
            model_storage_directory=str(model_root / 'easyocr'),
            user_network_directory=str(model_root / 'easyocr-user'),
        )
        with Image.new('RGB', (640, 120), 'white') as image:
            ImageDraw.Draw(image).text((20, 30), 'Hello world!',
                                      font=ImageFont.load_default(size=42), fill='black')
            with torch.inference_mode():
                recognized = reader.readtext(np.array(image), detail=0)
        assert 'hello world' in ' '.join(recognized).lower(), recognized
        report['checks']['english_ocr'] = {'status': 'passed', 'recognized': recognized}
        del reader

        engine = OpusMTEngine(model_root / 'opus-en-vi')
        translations = []
        for text in ('Hello world!', 'Thank you very much.', 'Where is the train station?'):
            result = engine.translate(text, 'en', 'vi')
            assert result and result.casefold() != text.casefold(), (text, result)
            translations.append({'source': text, 'translation': result})
        assert engine._translator.device == 'cpu'
        assert engine._translator.compute_type in ('int8', 'int8_float32')
        report['checks']['offline_translation'] = {
            'status': 'passed', 'compute_type': engine._translator.compute_type,
            'model_revision': engine.metadata['revision'], 'examples': translations,
        }
        report['status'] = 'passed'
    except Exception:
        report['error'] = traceback.format_exc()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root')
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    return run_release_checks(args.model_root, args.report)


if __name__ == '__main__':
    sys.exit(main())
