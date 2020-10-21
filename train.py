import argparse
import collections
import torch
import numpy as np
import data_loader.data_loaders as module_data
import data_loader.preprocess as module_preprocess
import model.loss as module_loss
import model.metric as module_metric
import model.model as module_arch
from parse_config import ConfigParser
from trainer.rnn_trainer import Trainer


# fix random seeds for reproducibility
SEED = 123
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
np.random.seed(SEED)


def main(config):
    logger = config.get_logger('train')
    # preprocess
    # config.init_obj('preprocess', module_preprocess)
    
    # setup data_loader instances
    data_loader = config.init_obj('data_loader', module_data, save_dir=config.save_dir)

    # build model architecture, then print to console
    encoder = config.init_obj(
        'encoder_arch', module_arch,
        vocab_size=data_loader.vocab_size,
        padding_idx=data_loader.padding_idx,
        hidden_size=config['hidden_size'],
        embed_size=config['embed_size']
    )
    logger.info(encoder)
    decoder = config.init_obj(
        'decoder_arch', module_arch,
        embedding=encoder.embedding,
        hidden_size=config['hidden_size'],
        vocab_size=data_loader.vocab_size
    )
    logger.info(decoder)
    model_idx = dict([('encoder', 0), ('decoder', 1)])
    models = [encoder, decoder]

    # get function handles of loss and metrics
    criterion = getattr(module_loss, config['loss'])
    metrics = [getattr(module_metric, met) for met in config['metrics']]

    # build optimizer, learning rate scheduler. delete every lines containing lr_scheduler for disabling scheduler
    optimizers = []
    lr_schedulers = []
    for idx in range(len(models)):
        trainable_params = filter(lambda p: p.requires_grad, models[idx].parameters())
        optimizer = config.init_obj('optimizer', torch.optim, trainable_params)
        lr_scheduler = config.init_obj('lr_scheduler', torch.optim.lr_scheduler, optimizer)
        optimizers += [optimizer]
        lr_schedulers += [lr_scheduler]

    trainer = Trainer(model_idx, models, criterion, metrics, optimizers,
                      config=config,
                      padding_idx=data_loader.padding_idx,
                      init_token=data_loader.init_token,
                      data_loader=data_loader.train_iter,
                      valid_data_loader=data_loader.valid_iter,
                      lr_scheduler=lr_scheduler
                      )

    trainer.train()


if __name__ == '__main__':
    args = argparse.ArgumentParser(description='PyTorch Template')
    args.add_argument('-c', '--config', default=None, type=str,
                      help='config file path (default: None)')
    args.add_argument('-r', '--resume', default=None, type=str,
                      help='path to latest checkpoint (default: None)')
    args.add_argument('-d', '--device', default=None, type=str,
                      help='indices of GPUs to enable (default: all)')

    # custom cli options to modify configuration from default values given in json file.
    CustomArgs = collections.namedtuple('CustomArgs', 'flags type target')
    options = [
        CustomArgs(['--lr', '--learning_rate'], type=float, target='optimizer;args;lr'),
        CustomArgs(['--bs', '--batch_size'], type=int, target='data_loader;args;batch_size')
    ]
    config = ConfigParser.from_args(args, options)
    main(config)
