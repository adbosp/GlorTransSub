"""Offline engine routing/resource checks; pretrained smoke is opt-in via env."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from opus_mt import MANIFEST, OpusMTEngine
from smart_translator import SmartTranslator
from test_runtime_resources import OfflineGoogle, load_workers


class OfflineTranslation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        metadata = dict(format_version=1, source_lang='en', target_lang='vi',
                        eos_token='</s>', special_tokens=['</s>', '<pad>', '<unk>'])
        (self.root / MANIFEST).write_text(json.dumps(metadata), encoding='utf-8')
        # These placeholders test validation/routing, never real inference.
        for name in ('model.bin', 'config.json', 'source.spm', 'target.spm'):
            (self.root / name).touch()

    def translator(self):
        with patch('smart_translator.GoogleEngine', OfflineGoogle):
            return SmartTranslator()

    def test_optional_runtime_is_lazy(self):
        engine = OpusMTEngine(self.root)
        self.assertIsNone(engine._translator)
        self.assertEqual(engine.source_lang, 'en')
        self.assertEqual(engine.target_lang, 'vi')

    def test_missing_model_stays_offline_even_after_resume(self):
        translator = self.translator()
        with self.assertRaises(ValueError):
            translator.configure('opus_mt', model=str(self.root / 'missing'))
        translator.resume()
        self.assertEqual(translator.translate('Hello', 'en', 'vi'), '')
        self.assertEqual(translator._google.calls, 0)
        self.assertEqual(translator.engine_name, 'opus_mt')

    def test_corrected_model_folder_can_be_applied_after_validation_failure(self):
        translator = self.translator()
        manifest = self.root / MANIFEST
        saved_manifest = manifest.read_text(encoding='utf-8')
        manifest.unlink()
        with self.assertRaises(ValueError):
            translator.configure('opus_mt', model=str(self.root))
        manifest.write_text(saved_manifest, encoding='utf-8')
        translator.configure('opus_mt', model=str(self.root))
        self.assertIsInstance(translator._engine, OpusMTEngine)

    def test_wrong_pair_fails_before_loading(self):
        engine = OpusMTEngine(self.root)
        for src, tgt in [('auto', 'vi'), ('en', 'ja'), ('vi', 'en')]:
            with self.subTest(src=src, tgt=tgt):
                with self.assertRaisesRegex(ValueError, 'supports en'):
                    engine.translate('Hello', src, tgt)
        self.assertIsNone(engine._translator)

    def test_local_failure_never_calls_google(self):
        translator = self.translator()
        translator.configure('opus_mt', model=str(self.root))
        with patch.object(translator._engine, '_load', side_effect=RuntimeError('missing runtime')):
            self.assertEqual(translator.translate('Hello', 'en', 'vi'), '')
        self.assertIn('missing runtime', translator.last_error)
        self.assertEqual(translator._google.calls, 0)

    def test_apply_same_model_reuses_loaded_engine(self):
        translator = self.translator()
        translator.configure('opus_mt', model=str(self.root))
        engine = translator._engine
        translator.configure('opus_mt', model=str(self.root))
        self.assertIs(translator._engine, engine)
        translator.configure('google')
        self.assertIs(translator._engine, translator._google)

    def test_split_long_input_preserves_lines_and_does_not_truncate(self):
        engine = OpusMTEngine(self.root)
        engine._normalizer = lambda text: text
        engine._source = Mock()
        engine._source.encode.side_effect = lambda line, out_type: line.split()
        engine._target = Mock()
        engine._target.decode.side_effect = lambda pieces: ' '.join(pieces)
        engine._translator = Mock()
        engine._translator.translate_batch.side_effect = lambda batch, **kwargs: [
            Mock(hypotheses=[batch[0]])]
        text = ' '.join(f'token{i}' for i in range(600)) + '\nHello world'
        self.assertEqual(engine.translate(text, 'en', 'vi'), text)
        self.assertEqual(engine._translator.translate_batch.call_count, 4)
        for call in engine._translator.translate_batch.call_args_list:
            self.assertLessEqual(len(call.args[0][0]), 257)
            self.assertEqual(call.args[0][0][-1], '</s>')
            self.assertEqual(call.kwargs['max_input_length'], 0)

    def test_fixed_target_prefix_is_added_to_every_chunk(self):
        engine = OpusMTEngine(self.root)
        engine.metadata['source_prefix'] = '>>vie<<'
        engine._normalizer = lambda text: text
        engine._source = Mock()
        engine._source.encode.return_value = ['word'] * 300
        engine._target = Mock()
        engine._target.decode.return_value = 'Xin chao'
        engine._translator = Mock()
        engine._translator.translate_batch.return_value = [Mock(hypotheses=[['Xin', 'chao']])]
        self.assertEqual(engine.translate('Hello', 'en', 'vi'), 'Xin chao Xin chao')
        self.assertEqual(engine._translator.translate_batch.call_count, 2)
        for call in engine._translator.translate_batch.call_args_list:
            self.assertEqual(call.args[0][0][0], '>>vie<<')
            self.assertEqual(call.args[0][0][-1], '</s>')

    def test_context_markers_not_sent_to_local_model(self):
        translator = self.translator()
        translator.configure('opus_mt', model=str(self.root))
        scope = load_workers(translator)
        worker = scope['OCRWorker'](3)
        worker.configure_context(True, 'game', 10, 'Hello = Xin chao')
        with patch.object(translator._engine, 'translate', return_value='Xin chao') as translate:
            self.assertEqual(worker._translate_with_optional_context('Hello', 'hello', 'en', 'vi'), 'Xin chao')
        translate.assert_called_once_with('Hello', 'en', 'vi')

    def test_saved_offline_config_is_restored(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        tree.body = [node for node in tree.body if getattr(node, 'name', '') == 'configure_translator']
        translator = self.translator()
        scope = dict(translator=translator, cfg={}, AI_PROVIDERS={})
        exec(compile(tree, str(path), 'exec'), scope)
        scope['configure_translator']({'translate_engine': 'opus_mt',
                                       'opus_mt_model_dir': str(self.root)})
        self.assertEqual(translator.engine_name, 'opus_mt')


@unittest.skipUnless(os.environ.get('GLOSUB_OPUS_TEST_MODEL'), 'Pretrained OPUS model not selected')
class PretrainedOpusSmoke(unittest.TestCase):
    def test_actual_en_vi_cpu_int8_translation(self):
        engine = OpusMTEngine(os.environ['GLOSUB_OPUS_TEST_MODEL'])
        for text in ['Hello world!', 'Thank you very much.', 'Where is the train station?']:
            result = engine.translate(text, 'en', 'vi')
            self.assertTrue(result)
            self.assertNotEqual(result.casefold(), text.casefold())
            print(f'OPUS-MT en→vi: {text} => {result}')
        self.assertEqual(engine._translator.device, 'cpu')
        self.assertIn(engine._translator.compute_type, ('int8', 'int8_float32'))


@unittest.skipUnless(os.environ.get('GLOSUB_TEST_CT2_CONVERSION'), 'Optional conversion integration check')
class TinyMarianConversion(unittest.TestCase):
    def test_real_sentencepiece_conversion_and_int8_execution(self):
        # Synthetic random weights verify the complete machinery, not pretrained
        # translation quality. All artifacts stay in a temporary directory.
        import shutil
        import sentencepiece as spm
        import torch
        from transformers import MarianConfig, MarianMTModel, MarianTokenizer
        from prepare_opus_model import prepare_model
        torch.set_num_threads(2)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'synthetic'
            source.mkdir()
            corpus = root / 'corpus.txt'
            corpus.write_text(('Hello world! Thank you. Xin chao the gioi.\n' * 100), encoding='utf-8')
            spm.SentencePieceTrainer.train(input=str(corpus), model_prefix=str(root / 'sp'),
                                          vocab_size=64, hard_vocab_limit=False, pad_id=3,
                                          minloglevel=2)
            for name in ('source.spm', 'target.spm'):
                shutil.copyfile(root / 'sp.model', source / name)
            processor = spm.SentencePieceProcessor(model_file=str(root / 'sp.model'))
            pieces = [processor.id_to_piece(i) for i in range(processor.get_piece_size())
                      if processor.id_to_piece(i) != '<pad>'] + ['>>vie<<', '<pad>']
            vocab = {piece: i for i, piece in enumerate(pieces)}
            (source / 'vocab.json').write_text(json.dumps(vocab), encoding='utf-8')
            tokenizer = MarianTokenizer(source_spm=str(source / 'source.spm'),
                                        target_spm=str(source / 'target.spm'),
                                        vocab=str(source / 'vocab.json'),
                                        source_lang='en', target_lang='vi')
            config = MarianConfig(vocab_size=len(tokenizer), d_model=16,
                                  encoder_layers=1, decoder_layers=1,
                                  encoder_attention_heads=2, decoder_attention_heads=2,
                                  encoder_ffn_dim=32, decoder_ffn_dim=32,
                                  pad_token_id=vocab['<pad>'], eos_token_id=vocab['</s>'],
                                  decoder_start_token_id=vocab['<pad>'])
            MarianMTModel(config).save_pretrained(source)
            tokenizer.save_pretrained(source)
            output = root / 'converted'
            with patch('huggingface_hub.snapshot_download', return_value=str(source)):
                prepare_model('en', 'vi', output)
            engine = OpusMTEngine(output)
            self.assertEqual(engine.metadata['source_prefix'], '>>vie<<')
            self.assertIsInstance(engine.translate('Hello world!', 'en', 'vi'), str)
            self.assertEqual(engine._translator.device, 'cpu')
            self.assertIn(engine._translator.compute_type, ('int8', 'int8_float32'))
            self.assertEqual(engine._source.encode('Hello world!', out_type=str) + [tokenizer.eos_token],
                             tokenizer.convert_ids_to_tokens(tokenizer.encode('Hello world!')))


if __name__ == '__main__':
    unittest.main()
