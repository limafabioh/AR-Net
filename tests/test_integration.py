#!/usr/bin/env python3

import unittest
import os
import pathlib
import logging

## lazy imports ala fastai2 style (needed for nice print functionality)
from fastai.basics import *
from fastai.tabular.all import *

import arnet

log = logging.getLogger("AR-Net.test")
log.setLevel("WARNING")
log.parent.setLevel("WARNING")

DIR = pathlib.Path(__file__).parent.parent.absolute()
data_path = os.path.join(DIR, "ar_data")
data_name = os.path.join(data_path, "ar_3_ma_0_noise_0.100_len_10000")
results_path = os.path.join(data_path, "test_results")

EPOCHS = 3


class IntegrationTests(unittest.TestCase):
    verbose = False
    plot = False
    save = False

    def test_fakie(self):
        pass

    def test_everything_created_ar_data(self):
        self.save = True
        if self.save:
            if not os.path.exists(results_path):
                os.makedirs(results_path)
        df, data_config = arnet.load_from_file(data_path, data_name, load_config=True, verbose=self.verbose)

        # Hyperparameters
        n_epoch = 2
        valid_p = 0.2
        n_forecasts = 1  # Note: if more than one, must have a list of ar_param for each forecast target.
        sparsity = 0.3  # guesstimate

        # sparse AR: (for non-sparse, set sparsity to 1.0)
        ar_order = int(1 / sparsity * data_config["ar_order"])
        # to compute stats
        ar_params = arnet.pad_ar_params([data_config["ar_params"]], ar_order, n_forecasts)

        learn = arnet.init_ar_learner(
            series=df,
            ar_order=ar_order,
            n_forecasts=n_forecasts,
            valid_p=valid_p,
            sparsity=sparsity,
            ar_params=ar_params,
            verbose=self.verbose,
        )

        lr_at_min, _ = learn.lr_find(start_lr=1e-6, end_lr=1e2, num_it=400)
        log.info("lr at minimum: {}".format(lr_at_min))

        # Run Model
        # if you know the best learning rate:
        # learn.fit(n_epoch, 1e-2)
        # else use onecycle
        learn.fit_one_cycle(n_epoch=2, lr_max=lr_at_min / 10)

        # Look at Coeff
        coeff = arnet.coeff_from_model(learn.model)
        log.info("ar params", arnet.nice_print_list(ar_params))
        log.info("model weights", arnet.nice_print_list(coeff))
        # should be [0.20, 0.30, -0.50, ...]

        preds, y = learn.get_preds()
        if self.plot:
            learn.recorder.plot_loss()
            arnet.plot_weights(
                ar_val=len(ar_params[0]), weights=coeff[0], ar=ar_params[0], save=self.save, savedir=results_path
            )
            arnet.plot_prediction_sample(preds, y, num_obs=100, save=self.save, savedir=results_path)
            arnet.plot_error_scatter(preds, y, save=save, savedir=results_path)

        if self.save:
            # Optional:save and create inference learner
            learn.freeze()
            model_name = "ar{}_sparse_{:.3f}_ahead_{}_epoch_{}.pkl".format(ar_order, sparsity, n_forecasts, n_epoch)
            learn.export(fname=os.path.join(results_path, model_name))
            # can be loaded like this
            learn = arnet.load_learner(fname=os.path.join(results_path, model_name), cpu=True)
        # can unfreeze the model and fine_tune
        learn.unfreeze()
        learn.fit_one_cycle(1, lr_at_min / 100)

        if self.plot:
            learn.recorder.plot_loss()

        coeff2 = arnet.coeff_from_model(learn.model)
        log.info("ar params", arnet.nice_print_list(ar_params))
        log.info("model weights", arnet.nice_print_list(coeff))
        log.info("model weights2", arnet.nice_print_list(coeff2))
        arnet.plot_weights(
            ar_val=len(ar_params[0]), weights=coeff2[0], ar=ar_params[0], save=self.save, savedir=results_path
        )

        if self.save:
            os.rmdir(results_path)
