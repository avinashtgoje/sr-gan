"""
Utility code to be used in miscellaneous cases.
"""
import os
import random
import re
import time
import zipfile
from urllib.request import urlretrieve

import numpy as np
import torch
from scipy.stats import rv_continuous
from tensorboardX import SummaryWriter as SummaryWriter_

gpu = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')


class SummaryWriter(SummaryWriter_):
    """A custom version of the Tensorboard summary writer class."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.step = 0
        self.summary_period = 1

    def add_scalar(self, tag, scalar_value, global_step=None):
        """Add a scalar to the Tensorboard summary."""
        if global_step is None:
            global_step = self.step
        if self.step % self.summary_period == 0:
            super().add_scalar(tag, scalar_value, global_step)

    def add_histogram(self, tag, values, global_step=None, bins='auto'):
        """Add a histogram to the Tensorboard summary."""
        if global_step is None:
            global_step = self.step
        if self.step % self.summary_period == 0:
            super().add_histogram(tag, values, global_step, bins)

    def add_image(self, tag, img_tensor, global_step=None):
        """Add an image to the Tensorboard summary."""
        if global_step is None:
            global_step = self.step
        if self.step % self.summary_period == 0:
            super().add_image(tag, img_tensor, global_step)

    def is_summary_step(self):
        """Returns whether or not the current step is a summary step."""
        return self.step % self.summary_period == 0


def infinite_iter(dataset):
    """Create an infinite generator from a dataset."""
    while True:
        for examples in dataset:
            yield examples


def clean_scientific_notation(string):
    """Cleans up scientific notation to remove unneeded fluff digits."""
    regex = r'\.?0*e([+\-])0*([0-9])'
    string = re.sub(regex, r'e\g<1>\g<2>', string)
    string = re.sub(r'e\+', r'e', string)
    return string


def shuffled(list_):
    """A simple wrapper to make a *returning* version of random.shuffle()"""
    random.seed()
    random.shuffle(list_)
    return list_


def load(model_path):
    """
    Loads a model, and if GPU is not available, insures that the model only loads onto CPU.

    :param model_path: The path to the model to be loaded.
    :type model_path: str
    :return: The loaded model.
    :rtype: dict[T]
    """
    if torch.cuda.is_available():
        return torch.load(model_path, map_location=lambda storage, loc: storage)
    else:
        return torch.load(model_path)


class MixtureModel(rv_continuous):
    """Creates a combination distribution of multiple scipy.stats model distributions."""
    def __init__(self, submodels, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submodels = submodels

    def _pdf(self, x, **kwargs):
        pdf = self.submodels[0].pdf(x)
        for submodel in self.submodels[1:]:
            pdf += submodel.pdf(x)
        pdf /= len(self.submodels)
        return pdf

    def rvs(self, size):
        """Random variates of the mixture model."""
        submodel_choices = np.random.randint(len(self.submodels), size=size)
        submodel_samples = [submodel.rvs(size=size) for submodel in self.submodels]
        rvs = np.choose(submodel_choices, submodel_samples)
        return rvs


def seed_all(seed=None):
    """Seed every type of random used by the SRGAN."""
    random.seed(seed)
    np.random.seed(seed)
    if seed is None:
        seed = int(time.time())
    torch.manual_seed(seed)


def make_directory_name_unique(trial_directory):
    """If the desired directory name already exists, make a new directory name based of the desired name."""
    if os.path.exists(trial_directory):
        run_number = 1
        while os.path.exists(trial_directory + ' r{}'.format(run_number)):
            run_number += 1
        trial_directory += ' r{}'.format(run_number)
    return trial_directory


def to_normalized_range(tensor_: torch.Tensor) -> torch.Tensor:
    """Convert from 0-255 range to -1 to 1 range."""
    # noinspection PyTypeChecker
    return (tensor_ / 127.5) - 1


def to_image_range(tensor_: torch.Tensor) -> torch.Tensor:
    """Convert from -1 to 1 range to 0-255."""
    # noinspection PyTypeChecker
    return (tensor_ + 1) * 127.5


def real_numbers_to_bin_indexes(real_numbers: torch.Tensor, bins: torch.Tensor):
    """Converts a batch of real numbers to a batch of indexes for the bins the real numbers fall in."""
    _, indexes = (real_numbers.view(-1, 1) - bins.view(1, -1)).abs().min(dim=1)
    return indexes


def logits_to_bin_values(logits: torch.Tensor, bins: torch.Tensor):
    """Converts a batch of logits the bin values the highest logit corresponds to."""
    _, indexes = logits.max(dim=1)
    values = bins[indexes]
    return values


def logsumexp(inputs, dim=None, keepdim=False):
    """Numerically stable logsumexp.

    Args:
        inputs: A Variable with any shape.
        dim: An integer.
        keepdim: A boolean.

    Returns:
        Equivalent of log(sum(exp(inputs), dim=dim, keepdim=keepdim)).
    """
    # For a 1-D array x (any array along a single dimension),
    # log sum exp(x) = s + log sum exp(x - s)
    # with s = max(x) being a common choice.
    if dim is None:
        inputs = inputs.view(-1)
        dim = 0
    s, _ = torch.max(inputs, dim=dim, keepdim=True)
    outputs = s + (inputs - s).exp().sum(dim=dim, keepdim=True).log()
    if not keepdim:
        outputs = outputs.squeeze(dim)
    return outputs


def download_and_extract_file(directory, download_link, file_name='temporary', password=None):
    """Downloads and extracts a file from a URL."""
    urlretrieve(download_link, os.path.join(directory, file_name))
    with zipfile.ZipFile(os.path.join(directory, file_name), 'r') as zip_file:
        zip_file.extractall(directory, pwd=password)
    os.remove(os.path.join(directory, file_name))