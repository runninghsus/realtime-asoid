from numba import jit
import math
import numpy as np
from tqdm import notebook
from sklearn.preprocessing import StandardScaler
from numba.typed import List


@jit(nopython=True)
def fast_standardize(data):
    a_ = (data - np.mean(data)) / np.std(data)
    return a_


def fast_nchoose2(n, k):
    a = np.ones((k, n - k + 1), dtype=int)
    a[0] = np.arange(n - k + 1)
    for j in range(1, k):
        reps = (n - k + j) - a[j - 1]
        a = np.repeat(a, reps, axis=1)
        ind = np.add.accumulate(reps)
        a[j, ind[:-1]] = 1 - reps[1:]
        a[j, 0] = j
        a[j] = np.add.accumulate(a[j])
        return a


@jit(nopython=True, parallel=True)
def fast_running_mean(x, N):
    out = np.zeros_like(x, dtype=np.float64)
    dim_len = x.shape[0]
    for i in range(dim_len):
        if N % 2 == 0:
            a, b = i - (N - 1) // 2, i + (N - 1) // 2 + 2
        else:
            a, b = i - (N - 1) // 2, i + (N - 1) // 2 + 1
        a = max(0, a)
        b = min(dim_len, b)
        out[i] = np.mean(x[a:b])
    return out


@jit(nopython=True)
def np_apply_along_axis(func1d, axis, arr):
    assert arr.ndim == 2
    assert axis in [0, 1]
    if axis == 0:
        result = np.empty(arr.shape[1])
        for i in range(len(result)):
            result[i] = func1d(arr[:, i])
    else:
        result = np.empty(arr.shape[0])
        for i in range(len(result)):
            result[i] = func1d(arr[i, :])
    return result


@jit(nopython=True)
def np_mean(array, axis):
    return np_apply_along_axis(np.mean, axis, array)


@jit(nopython=True)
def np_std(array, axis):
    return np_apply_along_axis(np.std, axis, array)


@jit(nopython=True)
def angle_between(vector1, vector2):
    """ Returns the angle in radians between given vectors"""
    v1_u = unit_vector(vector1)
    v2_u = unit_vector(vector2)
    minor = np.linalg.det(
        np.stack((v1_u[-2:], v2_u[-2:]))
    )
    if minor == 0:
        sign = 1
    else:
        sign = -np.sign(minor)
    dot_p = np.dot(v1_u, v2_u)
    dot_p = min(max(dot_p, -1.0), 1.0)
    return sign * np.arccos(dot_p)


@jit(nopython=True)
def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)


@jit(nopython=True)
def fast_displacment(data, reduce=False):
    data_length = data.shape[0]
    if reduce:
        displacement_array = np.zeros((data_length, np.int64(data.shape[1] / 10)), dtype=np.float64)
    else:
        displacement_array = np.zeros((data_length, np.int64(data.shape[1] / 2)), dtype=np.float64)
    for r in range(data_length):
        if r < data_length - 1:
            if reduce:
                count = 0
                for c in range(np.int64(data.shape[1]/2 - 2), data.shape[1], np.int64(data.shape[1]/2)):
                    displacement_array[r, count] = np.linalg.norm(data[r + 1, c:c + 2] - data[r, c:c + 2])
                    count += 1
            else:
                for c in range(0, data.shape[1], 2):
                    displacement_array[r, np.int64(c / 2)] = np.linalg.norm(data[r + 1, c:c + 2] - data[r, c:c + 2])
    return displacement_array


@jit(nopython=True)
def fast_length_angle(data, index):
    data_length = data.shape[0]
    length_2d_array = np.zeros((data_length, index.shape[1], 2), dtype=np.float64)
    for r in range(data_length):
        for i in range(index.shape[1]):
            ref = index[0, i]
            target = index[1, i]
            length_2d_array[r, i, :] = data[r, ref:ref + 2] - data[r, target:target + 2]
    length_array = np.zeros((data_length, length_2d_array.shape[1]), dtype=np.float64)
    angle_array = np.zeros((data_length, length_2d_array.shape[1]), dtype=np.float64)
    for k in range(length_2d_array.shape[1]):
        for kk in range(data_length):
            length_array[kk, k] = np.linalg.norm(length_2d_array[kk, k, :])
            if kk < data_length - 1:
                try:
                    angle_array[kk, k] = np.rad2deg(
                        angle_between(length_2d_array[kk, k, :], length_2d_array[kk + 1, k, :]))
                except:
                    pass
    return length_array, angle_array


@jit(nopython=True)
def fast_smooth(data, n):
    data_boxcar_avg = np.zeros((data.shape[0], data.shape[1]))
    for body_part in range(data.shape[1]):
        data_boxcar_avg[:, body_part] = fast_running_mean(data[:, body_part], n)
    return data_boxcar_avg


@jit(nopython=True)
def fast_feature_extraction(data, framerate, index, smooth):
    window = np.int64(np.round(0.05 / (1 / framerate)) * 2 - 1)
    features = List()
    for n in range(len(data)):
        displacement_raw = fast_displacment(data[n])
        length_raw, angle_raw = fast_length_angle(data[n], index)
        if smooth:
            displacement_run_mean = fast_smooth(displacement_raw, window)
            length_run_mean = fast_smooth(length_raw, window)
            angle_run_mean = fast_smooth(angle_raw, window)
            features.append(np.hstack((length_run_mean[1:, :], angle_run_mean[:-1, :], displacement_run_mean[:-1, :])))
        else:
            features.append(np.hstack((length_raw[1:, :], angle_raw[:-1, :], displacement_raw[:-1, :])))
    return features


@jit(nopython=True)
def fast_feature_binning(features, framerate, index):
    binned_features_list = List()
    for n in range(len(features)):
        bin_width = np.int64(framerate / 10)
        for s in range(bin_width):
            binned_features = np.zeros((np.int64(features[n].shape[0] / bin_width), features[n].shape[1]), dtype=np.float64)
            for b in range(bin_width + s, features[n].shape[0], bin_width):
                binned_features[np.int64(b / bin_width - 1), 0:index.shape[1]] = np_mean(features[n][(b - bin_width):b,
                                                                                    0:index.shape[1]], 0)
                binned_features[np.int64(b / bin_width - 1), index.shape[1]:] = np.sum(features[n][(b - bin_width):b,
                                                                                  index.shape[1]:], axis=0)
            binned_features_list.append(binned_features)
    return binned_features_list


def bsoid_extract_numba(data, fps):
    smooth = False
    index = fast_nchoose2(int(data[0].shape[1] / 2), 2)
    # print(len(data)) # 1
    features = fast_feature_extraction(data, fps, index * 2, smooth)
    # print(len(features)) # 1
    binned_features = fast_feature_binning(features, fps, index * 2)
    # print(len(binned_features)) # 1
    return binned_features


def feature_extraction(train_datalist, num_train, framerate=120):
    f_integrated = []
    data_list = List()
    # for i in notebook.tqdm(range(num_train)):
    for i in range(num_train):
        data_list.append(train_datalist[i])
        binned_features = bsoid_extract_numba(data_list, framerate)
        f_integrated.append(binned_features[0])  # getting only the non-shifted
    features = np.vstack([f_integrated[m] for m in range(len(f_integrated))])
    scaler = StandardScaler()
    scaler.fit(features)
    scaled_features = scaler.transform(features)
    return features, scaled_features


def bsoid_predict_numba(feats, scaler, clf):
    """
    :param feats: list, multiple feats (original feature space)
    :param clf: Obj, MLP classifier
    :return nonfs_labels: list, label/100ms
    """
    labels_fslow = []
    for i in range(0, len(feats)):
        scaled_feats = scaler.transform(feats[i])
        labels = clf.predict(np.nan_to_num(scaled_feats))
        labels_fslow.append(labels)
    return labels_fslow


def frameshift_predict(data_test, num_test, scaler, rf_model, framerate=120):
    labels_fs = []
    new_predictions = []
    for i in range(num_test):
        feats_new = bsoid_extract_numba([data_test[i]], framerate)
        labels = bsoid_predict_numba(feats_new, scaler, rf_model)
        for m in range(0, len(labels)):
            labels[m] = labels[m][::-1]
        labels_pad = -1 * np.ones([len(labels), len(max(labels, key=lambda x: len(x)))])
        for n, l in enumerate(labels):
            labels_pad[n][0:len(l)] = l
            labels_pad[n] = labels_pad[n][::-1]
            if n > 0:
                labels_pad[n][0:n] = labels_pad[n - 1][0:n]
        labels_fs.append(labels_pad.astype(int))
    for k in range(0, len(labels_fs)):
        labels_fs2 = []
        for l in range(math.floor(framerate / 10)):
            labels_fs2.append(labels_fs[k][l])
        new_predictions.append(np.array(labels_fs2).flatten('F'))
    new_predictions_pad = []
    for i in range(0, len(new_predictions)):
        new_predictions_pad.append(np.pad(new_predictions[i], (len(data_test[i]) -
                                                               len(new_predictions[i]), 0), 'edge'))
    return np.hstack(new_predictions_pad)


def unison_shuffled_copies(a, b, s):
    assert len(a) == len(b)
    np.random.seed(s)
    p = np.random.permutation(len(a))
    return a[p], b[p]