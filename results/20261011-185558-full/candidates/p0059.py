import numpy as np

def priority(item, bins, capacity):
    c, m = item[0], item[1]
    cap_c, cap_m = capacity[0], capacity[1]
    rc = bins[:, 0].astype(float)
    rm = bins[:, 1].astype(float)
    
    # Remaining after placement
    after_c = rc - c
    after_m = rm - m
    
    # Normalized remaining after placement
    f_c = after_c / cap_c
    f_m = after_m / cap_m
    
    max_l = np.maximum(f_c, f_m)
    min_l = np.minimum(f_c, f_m)
    
    # Normalized dot product of item and pre-placement remaining
    dot_norm = (c * rc + m * rm) / (cap_c * cap_m)
    
    # Combine: compactness and balance (negative), plus alignment bonus
    score = -max_l - 0.5 * (max_l - min_l) + 0.5 * dot_norm
    
    return score
