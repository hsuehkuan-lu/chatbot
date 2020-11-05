import re
import os
import csv
import codecs
import unicodedata
import torch
from torchvision import datasets, transforms
from base import BaseDataLoader
import spacy
from torchtext.data import TabularDataset, Field, BucketIterator, Iterator


class MnistDataLoader(BaseDataLoader):
    """
    MNIST data loading demo using BaseDataLoader
    """
    def __init__(self, data_dir, batch_size, shuffle=True, validation_split=0.0, num_workers=1, training=True):
        trsfm = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])
        self.data_dir = data_dir
        self.dataset = datasets.MNIST(self.data_dir, train=training, download=True, transform=trsfm)
        super().__init__(self.dataset, batch_size, shuffle, validation_split, num_workers)


class ChatbotDataLoader(object):
    """
    Chatbot data loading
    """
    def __init__(self, data_dir, filename, save_dir, batch_size, sent_len, init_token, eos_token,
                 text_field_path=None, vocab_path=None, min_freq=5, shuffle=True, validation_split=0.0, debug=False):
        # create text field
        self.spacy_lang = spacy.load('en')
        self.TEXT = self._create_text_field(
            init_token=init_token,
            eos_token=eos_token,
            sent_len=sent_len,
            text_field_path=text_field_path,
            save_dir=save_dir
        )
        # create dataset
        self.debug = debug
        self.batch_size = batch_size
        self.sent_len = sent_len
        self.data_dir = data_dir
        self.dataset = self._create_dataset(filename)
        self.n_samples = len(self.dataset)
        # create vocab
        self._create_vocab(vocab_path, min_freq, save_dir)
        self.vocab_size = len(self.TEXT.vocab.itos)
        self.padding_idx = self.TEXT.vocab.stoi['<pad>']
        self.unk_idx = self.TEXT.vocab.stoi['<unk>']
        self.init_token = self.TEXT.vocab.stoi[init_token]
        # split data
        if 1 > validation_split > 0:
            self.train, self.valid = self.dataset.split(split_ratio=1. - validation_split)
            self.valid_iter = BucketIterator(self.valid, batch_size, sort_key=lambda x: len(x.talk),
                                             train=False, repeat=False)
        else:
            self.train = self.dataset
        self.train_iter = BucketIterator(self.train, batch_size, sort_key=lambda x: len(x.talk),
                                         shuffle=shuffle, repeat=False)

    def _preprocessing(self, text_arr):
        tokens = []
        text = unicodedata.normalize('NFC', ' '.join(text_arr)).strip()
        for tok in text.split():
            norm_tok = re.sub(r'[\W]', '', tok)
            if norm_tok:
                tokens += [norm_tok]
        return tokens

    def _postprocessing(self, text_arr, vocab):
        return list(filter(lambda x: len(x) < self.sent_len, text_arr))

    def _tokenizer(self, text):
        return [tok.text for tok in self.spacy_lang.tokenizer(text)]

    def _create_text_field(self, init_token, eos_token, sent_len, text_field_path, save_dir):
        if text_field_path:
            text_field = torch.load(text_field_path)
        else:
            text_field = Field(
                sequential=True,
                init_token=init_token,
                eos_token=eos_token,
                fix_length=sent_len,
                tokenize=self._tokenizer,
                include_lengths=True,
                lower=True,
                preprocessing=self._preprocessing
            )
        torch.save(text_field, os.path.join(save_dir, 'TEXT.Field'))
        return text_field

    def _create_dataset(self, filename):
        if self.debug:
            dataset = TabularDataset(
                path=os.path.join(self.data_dir, 'first_100_formatted_movie_lines.csv'),
                format='csv',
                fields={
                    'talk': ('talk', self.TEXT),
                    'response': ('response', self.TEXT)
                },
                csv_reader_params={'delimiter': '\t'},
                skip_header=False
            )
        else:
            dataset = TabularDataset(
                path=os.path.join(self.data_dir, filename),
                format='csv',
                fields={
                    'talk': ('talk', self.TEXT),
                    'response': ('response', self.TEXT)
                },
                csv_reader_params={'delimiter': '\t'},
                skip_header=False
            )
        return dataset

    def _create_vocab(self, vocab_path, min_freq, save_dir):
        if vocab_path:
            self.TEXT.vocab = torch.load(vocab_path)
        else:
            self.TEXT.build_vocab(self.dataset, min_freq=min_freq)
        torch.save(self.TEXT.vocab, os.path.join(save_dir, 'TEXT.Vocab'))


class InferenceChatbotDataLoader(object):
    """
    Inference Chatbot data loading
    """
    def __init__(self, text_field_path, vocab_path):
        # create text field
        self.TEXT = torch.load(text_field_path)
        self.TEXT.vocab = torch.load(vocab_path)
        self.vocab = self.TEXT.vocab.stoi
        self.id2tok = self.TEXT.vocab.itos
        self.vocab_size = len(self.TEXT.vocab.itos)
        self.padding_idx = self.TEXT.vocab.stoi['<pad>']
        self.init_idx = self.TEXT.vocab.stoi['<init>']
        self.end_idx = self.TEXT.vocab.stoi['<eos>']
        self.sent_len = self.TEXT.fix_length

    def preprocess(self, text):
        # if isinstance(text, str):
        #     text = [text]
        x = self.TEXT.preprocess(text)
        x = self.TEXT.pad([x])
        x = self.TEXT.numericalize(x)
        return x

    def convert_ids_to_text(self, ids):
        text = ids.T[0]
        tokens = []
        for tok in text:
            if tok == self.end_idx:
                break
            tokens += [self.id2tok[tok]]
        return ' '.join(tokens)
