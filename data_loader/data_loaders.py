import re
import os
import csv
import codecs
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


class ChatbotDataLoader(BaseDataLoader):
    """
    Chatbot data loading
    """
    def __init__(self, data_dir, filename, batch_size, sent_len, init_token, eos_token,
                 min_freq=5, shuffle=True, validation_split=0.0, num_workers=1,
                 training=True):
        self.spacy_lang = spacy.load('en')
        self.TEXT = Field(
            sequential=True,
            init_token=init_token,
            eos_token=eos_token,
            fix_length=sent_len,
            tokenize=self._tokenizer,
            lower=True
        )
        self.data_dir = data_dir
        self.dataset = TabularDataset(
            path=os.path.join(data_dir, filename),
            format='csv',
            fields={
                'talk': ('talk', self.TEXT),
                'response': ('response', self.TEXT)
            },
            csv_reader_params={'delimiter': '\t'},
            skip_header=False
        )
        self.TEXT.build_vocab(self.dataset, min_freq=min_freq)
        if training:
            self.data_iter = BucketIterator(
                self.dataset,
                batch_size,
                repeat=True
            )
        else:
            self.data_iter = Iterator(
                self.dataset,
                batch_size,
                repeat=True
            )
        super().__init__(self.data_iter, batch_size, shuffle, validation_split, num_workers)

    def _tokenizer(self, text):
        return [tok.text for tok in self.spacy_lang.tokenizer(text)]
