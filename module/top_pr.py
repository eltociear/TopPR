############################################################
################## Automatic Grid Search ###################
############################################################
def set_grid(data, grid_num = 100):
    import numpy as np

    # find min max
    dim = len(data[0])
    mins = np.array([])
    maxs = np.array([])
    for dims in range(dim):
        mins = np.append(mins, min(data[:,dims]))
        maxs = np.append(maxs, max(data[:,dims]))
    
    # set grid
    # 2 dimensional data
    if (len(mins) == 2):
        xval = np.linspace(mins[0], maxs[0], grid_num)
        yval = np.linspace(mins[1], maxs[1], grid_num)
        positions = np.array([[u,v] for u in xval for v in yval])
    # 3 dimensional data
    elif (len(mins) == 3):
        xval = np.linspace(mins[0], maxs[0], grid_num)
        yval = np.linspace(mins[1], maxs[1], grid_num)
        zval = np.linspace(mins[2], maxs[2], grid_num)
        positions = np.array([[u,v,k] for u in xval for v in yval for k in zval])
    
    return positions

############################################################
##################### Confidence Band ######################
############################################################
def confband_est(data, h, kernel = 'cosine', grid = 0, grid_num = 100, alpha = .1, repeat = 100, isnumpy = False, prob_est = False):
    # Set "p_hat = True" to return the estimated p_hat
    # Set "isnumpy = True" to return the not to transform the data into numpy
    # !!! We implement "p_hat" and "isnumpy" options for using this function in Bandwidth Estimator !!! #
    import numpy as np
    from sklearn.neighbors import KernelDensity
    import torch

    # data as numpy array
    if (isnumpy == False):
        if (isinstance(data, list) == True):
            data = np.asarray(data)
        elif (isinstance(data, tuple) == True):
            data = np.asarray(data)
        elif (torch.is_tensor(data) == True):
            for batch_idx, Input in enumerate(data):
                if (batch_idx == 0):
                    convert_data = Input.detach().numpy()
                else:
                    convert_data = np.vstack((convert_data, Input.detach().numpy()))
            data = convert_data
    elif (isnumpy == True): pass
    
    # automatically set grid
    if (len(grid) == 1):
        grid = set_grid(data, grid_num)

    # p_hat
    # non-compact kernel list = {'gaussian','exponential'} | compact kernel list = {'tophat','epanechnikov','linear','cosine'}
    KDE = KernelDensity(kernel = str(kernel), bandwidth = h)
    p_hat = np.exp(KDE.fit(data).score_samples(grid))
    
    # p_tilde
    theta_star = np.array([])
    for iloop in range(repeat):
        data_bs = data[np.random.choice(np.arange(len(data)), size = len(data), replace = True)]
        p_tilde = np.exp(KDE.fit(data_bs).score_samples(grid))
    
        # theta
        theta_star = np.append(theta_star, np.sqrt(len(data))*np.max(np.abs(p_hat-p_tilde)))
    
    # q_alpha
    q_range = np.linspace(min(theta_star), max(theta_star), 5000)
    q_alpha = np.array([])
    for q in q_range:
        if (((1/repeat)*sum(theta_star>=q)) <= alpha):
                q_alpha = np.append(q_alpha, q)
    q_alpha = np.min(q_alpha)
    
    # confidence band
    if (prob_est == False):
        return q_alpha/np.sqrt(len(data))
    else:
        return q_alpha/np.sqrt(len(data)), p_hat

############################################################
############### Band Width estimator H0 & H1 ###############
############################################################
def bandwidth_est(data, bandwidth_list, kernel = 'cosine', grid = 0, grid_num = 100, alpha = .1, Plot = False):
    # non-compact kernel list = {'gaussian','exponential'} | compact kernel list = {'tophat','epanechnikov','linear','cosine'}
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from tqdm import tqdm
    import gudhi
    import torch
    import matplotlib.pyplot as plot
    import seaborn as sns

    # match data format
    if (isinstance(data, list) == True):
        data = np.asarray(data)
    elif (isinstance(data, tuple) == True):
        data = np.asarray(data)
    elif (torch.is_tensor(data) == True):
        for batch_idx, Input in enumerate(data):
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        data = convert_data
    else: pass

    # automatically set grid
    if (grid == 0):
        grid = set_grid(data, grid_num)

    # estimate bandwidth
    n_h0 = np.array([])
    s_h0 = np.array([])
    n_h1 = np.array([])
    s_h1 = np.array([])
    for h in tqdm(bandwidth_list):
        # confidence band & p_hat
        cn, p_hat = confband_est(data, h, kernel = kernel, grid = grid, alpha = alpha, isnumpy = True, prob_est = True)

        # find significant homology
        PD = gudhi.CubicalComplex(dimensions = [round(len(grid)**(1/grid.shape[1])),round(len(grid)**(1/grid.shape[1]))],
                                 top_dimensional_cells = -p_hat).persistence()

        # measure life length of all homology
        l_h0 = np.array([])
        l_h1 = np.array([])
        for iloop in range(len(PD)):
            if (PD[iloop][0] == 0):
                if (np.abs(PD[iloop][1][1]-PD[iloop][1][0]) != float("inf")):
                    l_h0 = np.append(l_h0, np.abs(PD[iloop][1][1]-PD[iloop][1][0]))
            if (PD[iloop][0] == 1):
                l_h1 = np.append(l_h1, np.abs(PD[iloop][1][1]-PD[iloop][1][0]))
        
        # N(h)
        n_h0 = np.append(n_h0, sum(l_h0 > cn))
        n_h1 = np.append(n_h1, sum(l_h1 > cn))
        
        # S(h)
        S_h0 = l_h0 - cn
        S_h1 = l_h1 - cn
        s_h0 = np.append(s_h0, sum(list(filter(lambda S_h0 : S_h0 > 0, S_h0))))
        s_h1 = np.append(s_h1, sum(list(filter(lambda S_h1 : S_h1 > 0, S_h1))))
        print('bandwidth: ',h,', N_0(h): ',n_h0[-1],', S_0(h): ',s_h0[-1],', N_1(h): ',n_h1[-1],', S_1(h): ',s_h1[-1], ', cn: ',cn)

    if (Plot == True):
        fig = plot.figure(figsize = (18,2))
        for i in range(1,5):
            axes = fig.add_subplot(1,4,i)
            if (i == 1):
                axes.set_title(r"N(h) for $H_0$",fontsize = 15)
                plot.plot(bandwidth_list, n_h0, color = [133/255, 185/255, 190/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, n_h0, color = [133/255, 185/255, 190/255], s=100)
                
            elif (i == 2):
                axes.set_title(r"S(h) for $H_0$",fontsize = 15)
                plot.plot(bandwidth_list, s_h0, color = [255/255, 110/255, 97/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, s_h0, color = [255/255, 110/255, 97/255], s=100)
            
            elif (i == 3):
                axes.set_title(r"N(h) for $H_1$",fontsize = 15)
                plot.plot(bandwidth_list, n_h1, color = [133/255, 185/255, 190/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, n_h1, color = [133/255, 185/255, 190/255], s=100)
                
            elif (i == 4):
                axes.set_title(r"S(h) for $H_1$",fontsize = 15)
                plot.plot(bandwidth_list, s_h1, color = [255/255, 110/255, 97/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, s_h1, color = [255/255, 110/255, 97/255], s=100)

    return s_h0, s_h1, n_h0, n_h1

############################################################
################## Band Width estimator H0 #################
############################################################
def bandwidth_est_h0(data, bandwidth_list, confidence_band = False, kernel = 'cosine', grid = 0, grid_num = 100, alpha = .1, Plot = False):
    # non-compact kernel list = {'gaussian','exponential'} | compact kernel list = {'tophat','epanechnikov','linear','cosine'}
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from tqdm import tqdm
    import gudhi
    import torch
    import matplotlib.pyplot as plot
    import seaborn as sns    

    # match data format
    if (isinstance(data, list) == True):
        data = np.asarray(data)
    elif (isinstance(data, tuple) == True):
        data = np.asarray(data)
    elif (torch.is_tensor(data) == True):
        for batch_idx, Input in enumerate(data):
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        data = convert_data
    else: pass

    # automatically set grid
    if (grid == 0):
        grid = set_grid(data, grid_num)

    # estimate bandwidth
    n_h0 = np.array([])
    s_h0 = np.array([])
    cn_list = np.array([])
    for h in tqdm(bandwidth_list):
        # confidence band & p_hat
        cn, p_hat = confband_est(data, h, kernel = kernel, grid = grid, alpha = alpha, isnumpy = True, prob_est = True)
        cn_list = np.append(cn_list, cn)

        # find significant homology
        PD = gudhi.CubicalComplex(dimensions = [round(len(grid)**(1/grid.shape[1])),round(len(grid)**(1/grid.shape[1]))],
                                 top_dimensional_cells = -p_hat).persistence()
        
        # measure life length of all homology
        l_h0 = np.array([])
        for iloop in range(len(PD)):
            if (PD[iloop][0] == 0):
                if (np.abs(PD[iloop][1][1]-PD[iloop][1][0]) != float("inf")):
                    l_h0 = np.append(l_h0, np.abs(PD[iloop][1][1]-PD[iloop][1][0]))
        
        # N(h)
        n_h0 = np.append(n_h0, sum(l_h0 > cn)+1)
        
        # S(h)
        S_h0 = l_h0 - cn
        s_h0 = np.append(s_h0, sum(list(filter(lambda S_h0 : S_h0 > 0, S_h0))))
        print('bandwidth: ',h,', N_0(h): ',n_h0[-1],', S_0(h): ',s_h0[-1],', cn: ',cn)
    
    if (Plot == True):
        fig = plot.figure(figsize = (10,2))
        for i in range(1,3):
            axes = fig.add_subplot(1,2,i)
            if (i == 1):
                axes.set_title(r"N(h) for $H_0$",fontsize = 15)
                plot.plot(bandwidth_list, n_h0, color = [133/255, 185/255, 190/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, n_h0, color = [133/255, 185/255, 190/255], s=100)
                
            elif (i == 2):
                axes.set_title(r"S(h) for $H_0$",fontsize = 15)
                plot.plot(bandwidth_list, s_h0, color = [255/255, 110/255, 97/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, s_h0, color = [255/255, 110/255, 97/255], s=100)
        
    if (sum(s_h0 == max(s_h0)) == 1):
        if (confidence_band == True):
            return bandwidth_list[s_h0.tolist().index(max(s_h0))], cn_list[s_h0.tolist().index(max(s_h0))]
        elif (confidence_band == False):
            return bandwidth_list[s_h0.tolist().index(max(s_h0))]
    else: return 'cannot find the best h'

############################################################
################## Band Width estimator H1 #################
############################################################
def bandwidth_est_h1(data, bandwidth_list, confidence_band = False, kernel = 'cosine', grid = 0, grid_num = 100, alpha = .1, Plot = False):
    # non-compact kernel list = {'gaussian','exponential'} | compact kernel list = {'tophat','epanechnikov','linear','cosine'}
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from tqdm import tqdm
    import gudhi
    import torch
    import matplotlib.pyplot as plot
    import seaborn as sns

    # match data format
    if (isinstance(data, list) == True):
        data = np.asarray(data)
    elif (isinstance(data, tuple) == True):
        data = np.asarray(data)
    elif (torch.is_tensor(data) == True):
        for batch_idx, Input in enumerate(data):
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        data = convert_data
    else: pass

    # automatically set grid
    if (grid == 0):
        grid = set_grid(data, grid_num)
    
    # estimate bandwidth    
    n_h1 = np.array([])
    s_h1 = np.array([])
    cn_list = np.array([])
    for h in tqdm(bandwidth_list):
        # confidence band & p_hat
        cn, p_hat = confband_est(data, h, kernel = kernel, grid = grid, alpha = alpha, isnumpy = True, prob_est = True)
        cn_list = np.append(cn_list, cn)

        # find significant homology
        PD = gudhi.CubicalComplex(dimensions = [round(len(grid)**(1/grid.shape[1])),round(len(grid)**(1/grid.shape[1]))],
                                 top_dimensional_cells = -p_hat).persistence()
        
        # measure life length of all homology
        l_h1 = np.array([])
        for iloop in range(len(PD)):
            if (PD[iloop][0] == 1):
                l_h1 = np.append(l_h1, np.abs(PD[iloop][1][1]-PD[iloop][1][0]))

        # N(h)
        n_h1 = np.append(n_h1, sum(l_h1 > cn))
        
        # S(h)
        S_h1 = l_h1 - cn
        s_h1 = np.append(s_h1, sum(list(filter(lambda S_h1 : S_h1 > 0, S_h1))))
        print('bandwidth: ',h,', N_1(h): ',n_h1[-1],', S_1(h): ',s_h1[-1],', cn: ',cn)

    if (Plot == True):
        fig = plot.figure(figsize = (10,2))
        for i in range(1,3):
            axes = fig.add_subplot(1,2,i)
            if (i == 1):
                axes.set_title(r"N(h) for $H_1$",fontsize = 15)
                plot.plot(bandwidth_list, n_h1, color = [133/255, 185/255, 190/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, n_h1, color = [133/255, 185/255, 190/255], s=100)
                
            elif (i == 2):
                axes.set_title(r"S(h) for $H_1$",fontsize = 15)
                plot.plot(bandwidth_list, s_h1, color = [255/255, 110/255, 97/255], linestyle = '-', linewidth = 4)
                plot.scatter(bandwidth_list, s_h1, color = [255/255, 110/255, 97/255], s=100)
            
    if (sum(s_h1 == max(s_h1)) == 1):
        if (confidence_band == True):
            return bandwidth_list[s_h1.tolist().index(max(s_h1))], cn_list[s_h1.tolist().index(max(s_h1))]
        elif (confidence_band == False):
            return bandwidth_list[s_h1.tolist().index(max(s_h1))]
    else: return 'cannot find the best h'

############################################################
########### top_pr fitting only for real samples ###########
############################################################
def top_pr(real_features, fake_features, bandwidth_list, homology = 0, kernel = 'cosine', grid_num = 100, alpha = .1):
    # if homology = 0, then fits h with using H_0, when homology = 1 use H_1
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from sklearn.metrics import pairwise_distances
    import torch

    # match real data format
    if (isinstance(real_features, list) == True):
        real_features = np.asarray(real_features)
    elif (isinstance(real_features, tuple) == True):
        real_features = np.asarray(real_features)
    elif (torch.is_tensor(real_features) == True):
        for Input in real_features:
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        real_features = convert_data
    else: pass

    # match fake data format
    if (isinstance(fake_features, list) == True):
        fake_features = np.asarray(fake_features)
    elif (isinstance(fake_features, tuple) == True):
        fake_features = np.asarray(fake_features)
    elif (torch.is_tensor(fake_features) == True):
        for Input in fake_features:
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        fake_features = convert_data
    else: pass

    # find optimal bandwidth and corresponding confidence band
    if (homology == 0):
        bandwidth, conf_band= bandwidth_est_h0(data = real_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)
    elif (homology == 1):
        bandwidth, conf_band= bandwidth_est_h1(data = real_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)

    # estimation of manifold
    KDE = KernelDensity(kernel = 'gaussian', bandwidth = bandwidth)    
    KDE_r = KDE.fit(real_features)
    KDE_g = KDE.fit(fake_features)
    
    # count significant real samples on real manifold
    num_real = 0
    p_hat_rr = np.exp(KDE_r.score_samples(real_features))
    for iloop in range(len(p_hat_rr)):
        if (p_hat_rr[iloop] > conf_band):
            num_real = num_real + 1

    # count significant fake samples on real manifold
    num_fake_on_real = 0
    p_hat_gr = np.exp(KDE_r.score_samples(fake_features))
    for iloop in range(len(p_hat_gr)):
        if (p_hat_gr[iloop] > conf_band):
            num_fake_on_real = num_fake_on_real + 1
    
    # count significant fake samples on fake manifold
    num_fake = 0
    p_hat_gg = np.exp(KDE_g.score_samples(fake_features))
    for iloop in range(len(p_hat_gg)): 
        if (p_hat_gg[iloop] > conf_band):
            num_fake = num_fake + 1

    # count significant real samples on fake manifold
    num_real_on_fake = 0
    p_hat_rg = np.exp(KDE_g.score_samples(real_features))
    for iloop in range(len(p_hat_rg)):
        if (p_hat_rg[iloop] > conf_band):
            num_real_on_fake = num_real_on_fake + 1

    # topological precision
    if (num_real ==0):
        num_real = 0.00000000001
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])
    else:
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])

    # topological recall
    if (num_fake == 0):
        num_fake = 0.00000000001
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
    else:
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
        
    return t_precision, t_recall

############################################################
########## top_pr fitting for real & fake samples ##########
############################################################
def top_pr_rf(real_features, fake_features, bandwidth_list, homology = 0, kernel = 'cosine', grid_num = 100, alpha = .1):
    # if homology = 0, then fits h with using H_0, when homology = 1 use H_1
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from sklearn.metrics import pairwise_distances
    import torch

    # match real data format
    if (isinstance(real_features, list) == True):
        real_features = np.asarray(real_features)
    elif (isinstance(real_features, tuple) == True):
        real_features = np.asarray(real_features)
    elif (torch.is_tensor(real_features) == True):
        for Input in real_features:
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        real_features = convert_data
    else: pass

    # match fake data format
    if (isinstance(fake_features, list) == True):
        fake_features = np.asarray(fake_features)
    elif (isinstance(fake_features, tuple) == True):
        fake_features = np.asarray(fake_features)
    elif (torch.is_tensor(fake_features) == True):
        for Input in fake_features:
            if (batch_idx == 0):
                convert_data = Input.detach().numpy()
            else:
                convert_data = np.vstack((convert_data, Input.detach().numpy()))
        fake_features = convert_data
    else: pass

    # find optimal bandwidth and corresponding confidence band
    if (homology == 0):
        bandwidth_r, conf_band_r = bandwidth_est_h0(data = real_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)
        bandwidth_g, conf_band_g = bandwidth_est_h0(data = fake_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)
    elif (homology == 1):
        bandwidth_r, conf_band_r = bandwidth_est_h1(data = real_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)
        bandwidth_g, conf_band_g = bandwidth_est_h1(data = fake_features, bandwidth_list = bandwidth_list, 
            confidence_band = True, kernel = kernel, grid = 0, grid_num = grid_num, alpha = alpha, Plot = False)

    # estimation of manifold  
    KDE_r = KernelDensity(kernel = 'gaussian', bandwidth = bandwidth_r).fit(real_features)
    KDE_g = KernelDensity(kernel = 'gaussian', bandwidth = bandwidth_g).fit(fake_features)
    
    # count significant real samples on real manifold
    num_real = 0
    p_hat_rr = np.exp(KDE_r.score_samples(real_features))
    for iloop in range(len(p_hat_rr)):
        if (p_hat_rr[iloop] > conf_band_r):
            num_real = num_real + 1

    # count significant fake samples on real manifold
    num_fake_on_real = 0
    p_hat_gr = np.exp(KDE_r.score_samples(fake_features))
    for iloop in range(len(p_hat_gr)):
        if (p_hat_gr[iloop] > conf_band_r):
            num_fake_on_real = num_fake_on_real + 1
    
    # count significant fake samples on fake manifold
    num_fake = 0
    p_hat_gg = np.exp(KDE_g.score_samples(fake_features))
    for iloop in range(len(p_hat_gg)): 
        if (p_hat_gg[iloop] > conf_band_g):
            num_fake = num_fake + 1

    # count significant real samples on fake manifold
    num_real_on_fake = 0
    p_hat_rg = np.exp(KDE_g.score_samples(real_features))
    for iloop in range(len(p_hat_rg)):
        if (p_hat_rg[iloop] > conf_band_g):
            num_real_on_fake = num_real_on_fake + 1

    # topological precision
    if (num_real ==0):
        num_real = 0.00000000001
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])
    else:
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])

    # topological recall
    if (num_fake == 0):
        num_fake = 0.00000000001
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
    else:
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
        
    return t_precision, t_recall

'''
############################################################
###################### top_pr original #####################
############################################################
def top_pr(real_features, fake_features, conf_band, bandwidth):
    import numpy as np
    from sklearn.neighbors import KernelDensity
    from sklearn.metrics import pairwise_distances
    
    KDE = KernelDensity(kernel = 'gaussian', bandwidth = bandwidth)
    
    KDE_r = KDE.fit(real_features)
    num_real = 0
    p_hat_r = np.exp(KDE_r.score_samples(real_features))
    for iloop in range(len(p_hat_r)):
        if (p_hat_r[iloop] > conf_band):
            num_real = num_real + 1

    num_fake_on_real = 0
    p_hat_g = np.exp(KDE.score_samples(fake_features))
    for iloop in range(len(p_hat_g)):
        if (p_hat_g[iloop] > conf_band):
            num_fake_on_real = num_fake_on_real + 1
    if (num_real ==0):
        num_real = 0.00000000001
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])
    else:
        t_precision = min([(len(real_features) * num_fake_on_real) / (len(fake_features) * num_real),1])
    
    KDE_g = KDE.fit(fake_features)
    num_fake = 0
    p_hat_g = np.exp(KDE_g.score_samples(fake_features))
    for iloop in range(len(p_hat_g)): 
        if (p_hat_g[iloop] > conf_band):
            num_fake = num_fake + 1

    num_real_on_fake = 0
    p_hat_r = np.exp(KDE_g.score_samples(real_features))
    for iloop in range(len(p_hat_r)):
        if (p_hat_r[iloop] > conf_band):
            num_real_on_fake = num_real_on_fake + 1
    if (num_fake == 0):
        num_fake = 0.00000000001
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
    else:
        t_recall = min([(len(fake_features) * num_real_on_fake) / (len(real_features) * num_fake),1])
        
    return t_precision, t_recall
'''