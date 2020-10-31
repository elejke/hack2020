import os
import sys
import glob
import pathlib
import numpy as np
import pandas as pd
# import pylab as plt

from itertools import product

from lightgbm import LGBMClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.base import BaseEstimator, ClassifierMixin

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error as MAE

sys.path.append(os.path.abspath('../src/'))

from dpipe_metrics import get_matching
from dpipe_metrics import hausdorff_distance, surface_distances, dice_score, assd, iou

from matching_metrics import *

metrics_dict = {
    "dice_coefficient": {"2d": dice_score, "3d": dice_score},
#     "mae": {"2d": lambda x, y: np.abs(x - y).mean(), "3d": lambda x, y: np.abs(x - y).mean()},
#     "mse": {"2d": lambda x, y: ((x - y) ** 2).mean(), "3d": lambda x, y: ((x - y) ** 2).mean()},
    "hausdorff_distance": {"2d": hausdorff_distance, "3d": hausdorff_distance},
    "surface_distances": {"2d": surface_distances, "3d": surface_distances},
    "assd": {"2d": assd, "3d": assd}
}

unary_metrics_dict = {
    "area": {"2d": lambda x: (x > 0).sum(), "3d": lambda x: (x > 0).sum()}
}

matching_metrics_dict = {
    
    'match2predBinRate': {'function': match2predCoverageRate,
                          'params': {'coverage_binarization_threshold': list(np.arange(0.01, 0.7, 0.05)),
                                          'intersectionFunction':       [coverageCalculation,
                                                                         dm.dice_score,
                                                                         dm.iou]}},
    'match2gtBinRate': {'function': match2gtCoverageRate,
                        'params': {'coverage_binarization_threshold': list(np.arange(0.01, 0.7, 0.05)),
                                   'intersectionFunction':            [coverageCalculation,
                                                                       dm.dice_score,
                                                                       dm.iou]}},
    
    'gt_match_aggregator': {'function': gt_match_aggregator,
                    'params': { 'metric': [dm.iou],
                                'pred_instance_aggregator': [min, max],
                                'gt_instance_aggregator': [min, max]}},
    'pred_match_aggregator': {'function': pred_match_aggregator,
                              'params': {'metric': [dm.iou],
                                       'pred_instance_aggregator': [min, max],
                                       'gt_instance_aggregator': [min, max]}},
    'match2tpr': {'function': match2tpr,
                  'params':   {}}, 
    'match2fnr': {'function': match2fnr,
                  'params':   {}}, 
    'match2tp': {'function': match2tp,
                  'params':   {}}, 
}


class BaseQualityEstimator(BaseEstimator, ClassifierMixin):
    """Base Estimator for segmentation quality assessment"""

    def __init__(self, metrics=["dice_coefficient"], unary_metrics=["area"], matching_metrics=[], meta_clf=LGBMClassifier()):
        """
        Args:
            metrics: list of strings: metrics to be computed on pairs of preds and gt
            unary_metrics: list of string: metrics to be computed on preds directly
        
        TODO: params??
        """
        self.meta_clf = meta_clf
        self.metrics = list(filter(lambda _: _ in metrics_dict, metrics))
        self.unary_metrics = list(filter(lambda _: _ in unary_metrics_dict, unary_metrics))
        self.matching_metrics = list(filter(lambda _: _ in matching_metrics_dict, matching_metrics))
        
        self.data_type = "3d"
        self.X_metrics = None
    
    
    def fit(self, X, Xy=None, y=None):
        """
        
        """
        assert len(X) == len(Xy) == len(y)
        # get the dimensionality of the data
#         self.data_type = self._check_data_type(X)
        # compute all the metrics on the pairs from X (predictions) and Xy (gt)
        self.X_metrics = self._compute_metrics(X, Xy)
        # fit meta-classifier to metrics and human-made labels
        self.meta_clf.fit(self.X_metrics, y)

        return self
    
    def predict(self, X, Xy):
        
        X_metrics = self._compute_metrics(X, Xy)
        
        y_pred = self.meta_clf.predict(X_metrics)
        
        return y_pred
    
    def predict_proba(self, X, Xy):
        
        X_metrics = self._compute_metrics(X, Xy)
        
        y_pred = self.meta_clf.predict_proba(X_metrics)
        
        return y_pred
    
    def _compute_metrics(self, X, Xy):
        
        def _metrics(x, xy):
            metrics_computed = dict()
            for metric_ in self.metrics:
                metrics_computed[metric_] = metrics_dict[metric_][self.data_type](x, xy)
            return metrics_computed
        
        def _unary_metrics(x):
            unary_metrics_computed = dict()
            for metric_ in self.unary_metrics:
                unary_metrics_computed[metric_] = unary_metrics_dict[metric_][self.data_type](x)
            
            return unary_metrics_computed

        def _matching_metrics(x_decomp, xy_decomp):
            metric_ths = [0.02, 0.25, 0.7]
            matching = get_matching(x_decomp, xy_decomp, metric=iou, metric_ths=metric_ths)

            matching_metrics_computed = dict()
            for th, matching_ in zip(metric_ths, matching):
                for metric_ in self.matching_metrics:
                    if len(matching_metrics_dict[metric_]['params']) == 0:
                        matching_metrics_computed[metric_ + f'_iou_{th}'] = matching_metrics_dict[metric_][
                            'function'](matching_)
                    else:
                        params = matching_metrics_dict[metric_]['params']
                        #                     print(params)
                        #                     params = {"l": [1, 2, 3], "g": [4, 5, 6]}
                        params_sets = [dict(zip(params.keys(), v_)) for v_ in list(product(*params.values()))]
                        #                     params_sets = [dict(zip(params, t)) for t in zip(*params.values())]
                        #                     print(params_sets)
                        for param_set_ in params_sets:
                            temp_metric_name_ = metric_ + "_"
                            for key_ in param_set_:
                                temp_metric_name_ += str(param_set_[key_]) + "_" if isinstance(param_set_[key_],
                                                                                               float) or isinstance(
                                    param_set_[key_], int) else param_set_[key_].__name__
                            #                         print(temp_metric_name_)
                            matching_metrics_computed[temp_metric_name_ + f'_iou_{th}'] = \
                            matching_metrics_dict[metric_]['function'](matching_, **param_set_)
            #             print(len(matching_metrics_computed))
            return matching_metrics_computed

        metrics_computed = []
        
        for x_, xy_ in zip(X, Xy):
            metrics_temp_ = _metrics(x_[0], xy_[0])
            metrics_temp_.update(_unary_metrics(x_[0]))
            matching_metrics_temp_ = _matching_metrics(x_[1:], xy_[1:])
            metrics_temp_.update(matching_metrics_temp_)
            metrics_computed.append(metrics_temp_)
            
        df_metrics_computed = pd.DataFrame(metrics_computed)
        
        return df_metrics_computed
        
    def _check_data_type(self, X):
        """
        TODO:
        """
        # заглушка:
        if len(X.shape) == 2:
            return "2d"
        elif X.shape[2] == 1:
            return "2d"
        else:
            return "3d"

    def score(self, X, y=None):
        # counts number of values bigger than mean
        return(sum(self.predict(X))) 