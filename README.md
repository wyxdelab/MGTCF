# MGTCF
The code of "MGTCF: Multi-Generator Tropical Cyclone Forecasting with Heterogeneous Meteorological Data" accepted by AAAI2023.

In the process of sorting!
## Introduction
Contribution:

1.  MGTCF can utilize heterogeneous meteorologic data efficiently, including the inherent attribute data of TC and the meteorological grid data.
2. The Multi-generator and the GC-Net are used to tackle the prediction of undesired out-of-distribution samples and the insufficient learning ability of single-generator TC prediction methods. 
3. Env-Net improves the performance of TC prediction by embedding the environment information, which has been traditionally overlooked but is very important. To our knowledge, this is the first attempt to build a module focused on environment in TC prediction.
4. Extensive experiments were conducted on the China Meteorological Administration Tropical Cyclone Best Track Dataset (CMA-BST). 
We obtained state-of-the-art performance in deep learning methods and obtained better results than the method of the CMO in most indexes.

The explanation of ***cone of probability***:

When we use MMSTN to make a prediction of TC, we will generate k possible tendencies. By calculating these k possible tendencies, we obtain the ***cone of probability***. Like the figure showing below: 

![***cone of probability***](https://github.com/Zjut-MultimediaPlus/MMSTN/blob/main/Data/example24.png)

As for the calculation of evaluation criteria, we choose the **best prediction** through these k possible tendencies (including every time points) as our final prediction.

This is the source code of MMSTN.
## Requirements 
* python 3.8.5
* Pytorch 1.11.0
* CUDA 11.7
```python
##Install required libraries##
pip install -r requirements.txt
```
## Train
```python
##before train##
python -m visdom.server
##custom train##
python train.py
```
## Test
```python
## test on data of the year 2019##
python evaluate_model_ME.py --dset_type test2019
```
## Training new models
Instructions for training new models can be [found here](https://github.com/Zjut-MultimediaPlus/MMSTN/blob/main/TRAINING.md).

## The data we used
We used two open access dataset: [the CMA Tropical Cyclone Best Track Dataset](https://tcdata.typhoon.org.cn/en/zjljsjj_sm.html) 
and the results of [the CMO's tropical cyclone predictions](http://typhoon.nmc.cn/web.html).

To facilitate our readers, we arrange these data and upload them in [Data](https://github.com/Zjut-MultimediaPlus/MMSTN/tree/main/Data)

If you are interesting in these data, you can click [the CMA Tropical Cyclone Best Track Dataset](https://tcdata.typhoon.org.cn/en/zjljsjj_sm.html) and
[the CMO's tropical cyclone data](http://typhoon.nmc.cn/web.html) to obtain more details. 



## Note
Tropical cyclone prediction is a very difficult task. CMA dataset is not enough to train a perfect model to execute this task. MMSTN is a trivial but interesting attempt (cone of probability) for TC prediction. In order to make a better prediction of TC, expanding the training data with more information, including satellite cloud images, radar data, etc, maybe a good solution. Although, it also has its limitation. The data misalignment, the shortage of data with more information (only after the 2010s), and others are very tough difficulties and need us to tackle. If you have any advice or any questions, welcome to talk with me.

Our codes were modified from the implementation of ["Social GAN: Socially Acceptable Trajectories with Generative Adversarial Networks"](https://github.com/agrimgupta92/sgan). Please cite the two papers (SGAN and MMSTN) when you use the codes.
## Citing SGAN & MMSTN
```
@inproceedings{gupta2018social,
  title={Social GAN: Socially Acceptable Trajectories with Generative Adversarial Networks},
  author={Gupta, Agrim and Johnson, Justin and Fei-Fei, Li and Savarese, Silvio and Alahi, Alexandre},
  booktitle={IEEE Conference on Computer Vision and Pattern Recognition (CVPR)},
  number={CONF},
  year={2018}
}
```

```
@article{https://doi.org/10.1029/2021GL096898,
author = {Huang, Cheng and Bai, Cong and Chan, Sixian and Zhang, Jinglin},
title = {MMSTN: A Multi-Modal Spatial-Temporal Network for Tropical Cyclone Short-Term Prediction},
journal = {Geophysical Research Letters},
volume = {49},
number = {4},
pages = {e2021GL096898},
doi = {https://doi.org/10.1029/2021GL096898},
url = {https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2021GL096898},
year = {2022}
}
```
