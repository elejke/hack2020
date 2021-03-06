from functools import partial

import numpy as np
import dpipe_metrics as dm

def match2tpr(matches):

    gt_matches = matches[0]
    gt_unmatched = matches[2]

    n_gt_matched = len(gt_matches)
    n_gt_unmatched = len(gt_unmatched)

    return (n_gt_matched + 1) / (n_gt_matched + n_gt_unmatched + 1)


def match2tp(matches):

    gt_matches = matches[0]
    gt_unmatched = matches[2]

    n_gt_matched = len(gt_matches)
    n_gt_unmatched = len(gt_unmatched)

    return n_gt_matched


def match2fnr(matches):

    pred_matches = matches[1]
    pred_unmatched = matches[3]

    n_pred_matched = len(pred_matches)
    n_pred_unmatched = len(pred_unmatched)

    return n_pred_unmatched / (n_pred_matched + n_pred_unmatched + 1)

# ---

def _match_aggregator(matches, i, metric, pred_instance_aggregator, gt_instance_aggregator):
    assert (i == 0) or (i == 1)
    match = matches[i]
    if len(match) == 0:
        return np.NaN

    res = []
    for gt_inst_row in match:
        gt_inst_row_metrics = [metric(gt_inst_row[0], pred_inst) for pred_inst in gt_inst_row[1]]
        res.append(pred_instance_aggregator(gt_inst_row_metrics))

    return gt_instance_aggregator(res)

gt_match_aggregator = partial(_match_aggregator, i=0)
pred_match_aggregator = partial(_match_aggregator, i=1)


def coverageCalculation(x,y):
    return np.sum(x&y)/np.sum(x)

def match2gtCoverageRate(matches, 
                         coverage_binarization_threshold=0.7,
                         intersectionFunction=coverageCalculation):

    gt_matches = matches[0]
    gt_unmatched = matches[2]

    binary_coverage_instance_list = []
    for gt_instance_matching in gt_matches:
        instance = gt_instance_matching[0]
        predictions = gt_instance_matching[1]

        instance_coverage = intersectionFunction(instance, np.sum(predictions, axis=0, dtype=bool))
        binary_coverage_instance_list.append(instance_coverage>coverage_binarization_threshold)

    n_gt_matched = len(gt_matches)
    n_gt_unmatched = len(gt_unmatched)


    return np.sum(binary_coverage_instance_list) / (n_gt_matched + n_gt_unmatched + 1)


def match2predCoverageRate(matches, 
                           coverage_binarization_threshold = 0.3,
                           intersectionFunction=coverageCalculation):

    

    pred_matches   = matches[1]
    pred_unmatched = matches[3]

    binary_coverage_instance_list = []
    for pred_instance_matching in pred_matches:
        instance    = pred_instance_matching[0]
        gts         = pred_instance_matching[1]

        instance_coverage = intersectionFunction(instance, np.sum(gts, axis=0, dtype=bool))
        binary_coverage_instance_list.append(instance_coverage>coverage_binarization_threshold)

    n_pred_matched = len(pred_matches)
    n_pred_unmatched = len(pred_unmatched)


    return np.sum(binary_coverage_instance_list) / (n_pred_matched + n_pred_unmatched + 1)

#append distance metrics here
metricsSpecification = {'match2predBinRate': {'function': match2predCoverageRate,
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
                                            'params': { 'metric': [dm.iou, dm.l1_centres_distance, dm.l2_centres_distance],
                                                        'pred_instance_aggregator': [min, max, np.mean],
                                                        'gt_instance_aggregator': [min, max, np.mean]}},
                        'pred_match_aggregator': {'function': pred_match_aggregator,
                                                'params': {'metric': [dm.iou, dm.l1_centres_distance, dm.l2_centres_distance],
                                                           'pred_instance_aggregator': [min, max, np.mean],
                                                           'gt_instance_aggregator': [min, max, np.mean]}},
                        'match2tpr': {'function': match2tpr,
                                      'params':   {}}, 
                        'match2fnr': {'function': match2fnr,
                                      'params':   {}}, 
                        'match2tp': {'function': match2tp,
                                      'params':   {}},
                       }