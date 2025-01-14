import logging
import os
import math

import numpy as np
import cv2
import torch
from torch.utils.data import Dataset,DataLoader

# logger = logging.getLogger(__name__)


def env_data_processing(env_data):
    env_data_merge = {}
    batch = len(env_data)
    for key in env_data[0]:
        env_data_merge[key] = []
    for env_data_item in env_data:
        for key in env_data_item:
            env_data_merge[key].append(torch.tensor(env_data_item[key]))

    for key in env_data_merge:
        env_data_merge[key] = torch.stack(env_data_merge[key],dim=0).reshape(batch,-1).type(torch.float)

    return env_data_merge

def seq_collate(data):
    (obs_seq_list, pred_seq_list, obs_seq_rel_list, pred_seq_rel_list,
     non_linear_ped_list, loss_mask_list,obs_traj_Me, pred_traj_gt_Me, obs_traj_rel_Me, pred_traj_gt_rel_Me,
     obs_date_mask, pred_date_mask,image_obs,image_pre,env_data,tyID) = zip(*data)

    _len = [len(seq) for seq in obs_seq_list]
    cum_start_idx = [0] + np.cumsum(_len).tolist()
    seq_start_end = [[start, end]
                     for start, end in zip(cum_start_idx, cum_start_idx[1:])]

    # Data format: batch, input_size, seq_len
    # LSTM input format: seq_len, batch, input_size
    obs_traj = torch.cat(obs_seq_list, dim=0).permute(2, 0, 1)
    pred_traj = torch.cat(pred_seq_list, dim=0).permute(2, 0, 1)
    obs_traj_rel = torch.cat(obs_seq_rel_list, dim=0).permute(2, 0, 1)
    pred_traj_rel = torch.cat(pred_seq_rel_list, dim=0).permute(2, 0, 1)
    non_linear_ped = torch.cat(non_linear_ped_list)
    loss_mask = torch.cat(loss_mask_list, dim=0)
    seq_start_end = torch.LongTensor(seq_start_end)
    obs_traj_Me = torch.cat(obs_traj_Me, dim=0).permute(2, 0, 1)
    pred_traj_Me = torch.cat(pred_traj_gt_Me, dim=0).permute(2, 0, 1)
    obs_traj_rel_Me = torch.cat(obs_traj_rel_Me, dim=0).permute(2, 0, 1)
    pred_traj_rel_Me = torch.cat(pred_traj_gt_rel_Me, dim=0).permute(2, 0, 1)
    obs_date_mask = torch.cat(obs_date_mask, dim=0).permute(2, 0, 1)
    pred_date_mask = torch.cat(pred_date_mask, dim=0).permute(2, 0, 1)
    image_obs = torch.stack(image_obs, dim=0).permute(0,4,1,2,3)
    image_pre = torch.stack(image_pre, dim=0).permute(0,4,1,2,3)
    env_data = env_data_processing(env_data)
    out = [
        obs_traj, pred_traj, obs_traj_rel, pred_traj_rel, non_linear_ped,
        loss_mask, seq_start_end, obs_traj_Me, pred_traj_Me, obs_traj_rel_Me, pred_traj_rel_Me,
        obs_date_mask,pred_date_mask,image_obs,image_pre, env_data,tyID
    ]

    return tuple(out)




def read_file(_path, delim='\t'):    
    data = []
    add = []
    if delim == 'tab':
        delim = '\t'
    elif delim == 'space':
        delim = ' '
    with open(_path, 'r') as f:
        for line in f:    //读取文件的每一行
            line = line.strip().split(delim)    将每一行按照delim分割为列表，delim是txt文件中数据的分割符
            add.append(line[-2:])        //向add中添加每一行最后两项数据
            line = [float(i) for i in line[:-2]]    //把每一行除最后两项外其他项转化为float类型
            data.append(line)        //向data中添加每一行除最后两项外的其他项
    return {'main':np.asarray(data),'addition':add}          //把data的数据由列表转化为numpy.ndarray类型，其实data包含观测数据，add包含观测时间和台风名


def poly_fit(traj, traj_len, threshold):
    """
    Input:
    - traj: Numpy array of shape (2, traj_len)
    - traj_len: Len of trajectory
    - threshold: Minimum error to be considered for non linear traj
    Output:
    - int: 1 -> Non Linear 0-> Linear
    """
    t = np.linspace(0, traj_len - 1, traj_len)    //一维numpy数组，0~11
    res_x = np.polyfit(t, traj[0, -traj_len:], 2, full=True)[1]    //x轴为序号，y轴为经度，拟合一个二次函数，输出结果是一个一维numpy数组，包含二次函数每一项的系数
    res_y = np.polyfit(t, traj[1, -traj_len:], 2, full=True)[1]    //x轴为序号，y轴为纬度，取的是20帧观测数据的后12个                实际取得是一次项系数
    if res_x + res_y >= threshold:
        return 1.0
    else:
        return 0.0


class TrajectoryDataset(Dataset):
    """Dataloder for the Trajectory datasets"""
    def __init__(
        self, data_dir, obs_len=8, pred_len=12, skip=1, threshold=0.002,
        min_ped=1, delim='\t',other_modal='gph'
    ):
        """
        Args:
        - data_dir: Directory containing dataset files in the format
        <frame_id> <ped_id> <x> <y>
        - obs_len: Number of time-steps in input trajectories
        - pred_len: Number of time-steps in output trajectories
        - skip: Number of frames to skip while making the dataset
        - threshold: Minimum error to be considered for non linear traj
        when using a linear predictor
        - min_ped: Minimum number of pedestrians that should be in a seqeunce
        - delim: Delimiter in the dataset files
        """
        super(TrajectoryDataset, self).__init__()

        self.data_dir = data_dir
        self.obs_len = obs_len
        self.pred_len = pred_len
        self.skip = skip
        self.seq_len = self.obs_len + self.pred_len
        self.delim = delim
        self.modal_name = other_modal

        all_files = os.listdir(self.data_dir)    //得到文件目录下所有文件名组成的列表
        all_files = [os.path.join(self.data_dir, _path) for _path in all_files]    //将列表中所有文件的路径添加至所在文件目录路径，类似于绝对路径
        num_peds_in_seq = []
        seq_list = []
        seq_list_rel = []
        seq_list_date_mask = []
        loss_mask_list = []
        non_linear_ped = []
        tyID = []

        # 迭代读取文件夹中的txt文件
        for path in all_files:
            _,x = os.path.split(path)    //将文件的绝对路径分割，x是文件名
            tyname = os.path.splitext(x)[0]    //将文件名中除去扩展名的前半部分提取出来
            data = read_file(path, delim)       //将文件中的txt数据处理，把观测数据和附加数据分割开，返回字典data
            addinf = data['addition']    //包含时间和台风名字的列表
            data = data['main']    //包含观测数据的numpy类型的二维数组
            frames = np.unique(data[:, 0]).tolist()    //把序号的结构转换为列表
            frame_data = []
            for frame in frames:    //frame是序号
                # 将txt文件中同一帧的，没有目标的坐标点保存在同一个frame_data的同一个index中
                frame_data.append(data[frame == data[:, 0], :])                //将该序号所在行的观测值加入frame_data列表，最后列表的每一项代表一帧的观测数据，数据类型是一维numpy数组
            # 获取一个txt文件中的轨迹可以分割成多少个子轨迹，如第一个子轨迹：1,2,3...20，第二2,3,4，...21
            num_sequences = int(
                math.ceil((len(frames) - self.seq_len + 1) / skip))    //seqlen的意思是子轨迹的长度，skip分割子轨迹时跳跃的步数，skip=1就是如上举例的第一和第二个子轨迹
            # 迭代子轨迹                                                //num_sequences就是子轨迹的个数
            for idx in range(0, num_sequences * self.skip + 1, skip):    //遍历每个子轨迹，idx是子轨迹开头的序号
                # axis=0  照着row的方向叠在一起
                curr_seq_data = np.concatenate(
                    frame_data[idx:idx + self.seq_len], axis=0)        //把一个子轨迹的观测数据组合为numpy二维数组，每一行是一帧的观测数据，行数是帧数
                # peds_in_curr_seq  存储当前子序列的目标id，   ty的话   应该就是1
                peds_in_curr_seq = np.unique(curr_seq_data[:, 1])    //就是1
                curr_seq_rel = np.zeros((len(peds_in_curr_seq), 4,   // (1,4,20)
                                         self.seq_len))
                curr_seq = np.zeros((len(peds_in_curr_seq), 4, self.seq_len))    //(1,4,20)
                curr_loss_mask = np.zeros((len(peds_in_curr_seq),            //(1,20)
                                           self.seq_len))
                # 获取时间信息
                curr_date_mask = np.zeros((len(peds_in_curr_seq), 4, self.seq_len))    //(1,4,20)
                num_peds_considered = 0
                _non_linear_ped = []
                for _, ped_id in enumerate(peds_in_curr_seq):    //ped_id=1    循环的目的是每一次循环处理一批第二列相同的观测数据
                    curr_ped_seq = curr_seq_data[curr_seq_data[:, 1] ==
                                                 ped_id, :]        //把第二列等于ped_id的观测数据保存为二维numpy数组
                    curr_ped_seq = np.around(curr_ped_seq, decimals=4)    //将观测数据保留4位小数
                    pad_front = frames.index(curr_ped_seq[0, 0]) - idx    //对于第一个子轨迹，pad_front=0，第二个子轨迹pad_front=0，所以pad_front固定为0
                    pad_end = frames.index(curr_ped_seq[-1, 0]) - idx + 1    //pad_end固定为20
                    if pad_end - pad_front != self.seq_len:    //忽略不够seq_len长度的子轨迹，只使用行数为20即有20帧观测数据的子轨迹
                        continue
                    curr_ped_seq = np.transpose(curr_ped_seq[:, 2:])    //选取观测数据的2、3、4、5列，然后转置，得到的numpy数组每一列是一帧观测数据，行数是4，列数是20
                    curr_ped_seq = curr_ped_seq                         //此时得到的numpy数组才是真正用于训练的数据，共有4种数据

                    curr_ped_date_mask = [x[0] for x in addinf[idx:idx+pred_len+obs_len]]        //选取子轨迹中的时间数据，20个，组成列表
                    curr_ped_date_mask = self.embed_time(curr_ped_date_mask)    //将时间数据归一化处理，并修改格式为(1,4,20)的numpy数组
                    # Make coordinates relative
                    # rel_curr_ped_seq 存相邻两个坐标点中间的差  后-前
                    rel_curr_ped_seq = np.zeros(curr_ped_seq.shape)    //(4,20)
                    rel_curr_ped_seq[:, 1:] = \
                        curr_ped_seq[:, 1:] - curr_ped_seq[:, :-1]    //计算的是后一天减前一天的数据之差，四种数据都减，如1减0，19减18，得到的numpy数组第一列全0
                    _idx = num_peds_considered    //0
                    curr_seq[_idx, :, pad_front:pad_end] = curr_ped_seq    //shape=(1,4,20)，存储子轨迹的四种数据
                    curr_seq_rel[_idx, :, pad_front:pad_end] = rel_curr_ped_seq    //shape=(1,4,20)，存储相邻帧的数据之差，第一列全0
                    curr_date_mask[_idx, :, pad_front:pad_end] = curr_ped_date_mask    //shape=(1,4,20)，存储归一化的时间数据
                    # Linear vs Non-Linear Trajectory
                    _non_linear_ped.append(
                        poly_fit(curr_ped_seq, pred_len, threshold))    //(1,4,20) ，12，0.002    这里意思是1的时候经度和纬度在时间上都是非线性的，0反之
                    curr_loss_mask[_idx, pad_front:pad_end] = 1    //
                    num_peds_considered += 1

                # if num_peds_considered > min_ped: 源码---
                # - min_ped: Minimum number of pedestrians that should be in a seqeunce
                # 最小的行人个数，1的话  应该是至少有一个  但是源码缺大于1，有点问题。。。
                # 但是因为台风基本上同个时间都只有一个，所以我改成>=1
                if num_peds_considered >= min_ped:
                    non_linear_ped += _non_linear_ped
                    num_peds_in_seq.append(num_peds_considered)
                    loss_mask_list.append(curr_loss_mask[:num_peds_considered])
                    seq_list.append(curr_seq[:num_peds_considered])
                    seq_list_rel.append(curr_seq_rel[:num_peds_considered])
                    seq_list_date_mask.append(curr_date_mask[:num_peds_considered])
                    tyID.append({'old':[tyname,idx],'new':addinf[idx+self.obs_len-1],
                                 'tydate':[x[0] for x in addinf[idx:idx+pred_len+obs_len]]})

        self.num_seq = len(seq_list)    //子轨迹的数量
        seq_list = np.concatenate(seq_list, axis=0)
        seq_list_rel = np.concatenate(seq_list_rel, axis=0)
        seq_list_date_mask = np.concatenate(seq_list_date_mask, axis=0)
        loss_mask_list = np.concatenate(loss_mask_list, axis=0)
        non_linear_ped = np.asarray(non_linear_ped)

        # Convert numpy -> Torch Tensor
        self.obs_traj = torch.from_numpy(
            seq_list[:, :2, :self.obs_len]).type(torch.float)
        self.pred_traj = torch.from_numpy(
            seq_list[:, :2, self.obs_len:]).type(torch.float)
        self.obs_traj_rel = torch.from_numpy(
            seq_list_rel[:, :2, :self.obs_len]).type(torch.float)
        self.pred_traj_rel = torch.from_numpy(
            seq_list_rel[:, :2, self.obs_len:]).type(torch.float)
        self.obs_traj_Me = torch.from_numpy(
            seq_list[:, 2:, :self.obs_len]).type(torch.float)
        self.pred_traj_Me = torch.from_numpy(
            seq_list[:, 2:, self.obs_len:]).type(torch.float)
        self.obs_traj_rel_Me = torch.from_numpy(
            seq_list_rel[:, 2:, :self.obs_len]).type(torch.float)
        self.pred_traj_rel_Me = torch.from_numpy(
            seq_list_rel[:, 2:, self.obs_len:]).type(torch.float)
        self.loss_mask = torch.from_numpy(loss_mask_list).type(torch.float)
        self.non_linear_ped = torch.from_numpy(non_linear_ped).type(torch.float)

        self.obs_date_mask = torch.from_numpy(
            seq_list_date_mask[:, :, :self.obs_len]).type(torch.float)
        self.pred_date_mask = torch.from_numpy(
            seq_list_date_mask[:, :, self.obs_len:]).type(torch.float)

        cum_start_idx = [0] + np.cumsum(num_peds_in_seq).tolist()
        # seq_start_end 一个元组的索引代表的是同子序列中不同id的轨迹
        self.seq_start_end = [
            (start, end)
            for start, end in zip(cum_start_idx, cum_start_idx[1:])
        ]
        self.tyID = tyID

    def __len__(self):    //子轨迹的数量作为类的长度
        return self.num_seq

    def embed_time(self,date_list):       //传入的是子轨迹的时间数据列表，共20项
        data_embed = []
        for date in date_list:
            year = (float(date[:4]) - 1949) / (2019 - 1949) - 0.5
            month = (float(date[4:6]) - 1) / 11.0 - 0.5
            day = (float(date[6:8]) - 1) / 30.0 - 0.5
            hour = float(date[8:10]) / 18 - 0.5
            data_embed.append([year, month, day, hour])
        return np.array(data_embed).transpose(1, 0)[np.newaxis, :, :]        //将时间数据转换为每一列是一帧的时间数据，行数是4，列数代表帧数，有20帧，(1,4,20)

    def transforms(self,img):
        # mean=np.array([111.2762205937308])
        # std = np.array([59.03717801611257])
        # return (img-mean)/std
        modal_range = {'gph': (44490.578125,58768.4486860389),
                      'mcc': (0,1),
                      '10v': (-48.2635498046875, 53.091079711914055),
                      '10u': (-49.08894348144531, 47.56512451171875),
                      'sst': (273,312),
                      '100v': '/home/hc/Desktop/hca6000/TYDataset/wind_year_V100_centercrop',
                      '100u': '/home/hc/Desktop/hca6000/TYDataset/wind_year_U100_centercrop',
                      }


        all_min,all_max = modal_range[self.modal_name]
        img = (img-all_min)/(all_max-all_min)
        img[img>1] = 1
        img[img<0] = 0
        return img

    def img_read(self,img_path):
        # print(img_path)

        # img = cv2.imread(img_path)
        # img = cv2.resize(img,(128,64))
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = np.load(img_path)
        img = cv2.resize(img,(64,64))
        img = self.transforms(img)
        img = img[:,:,np.newaxis]

        return img

    def get_img(self,tyid_dic):
        tyname = tyid_dic['new'][1]
        year = tyid_dic['old'][0][2:6]
        tydate = tyid_dic['tydate']

        env_root = r'G:\data\AAAI_data\env_data\norm'
        env_date = tyid_dic['new'][0]
        env_path = os.path.join(env_root,year,tyname,env_date+'.npy')
        env_data = np.load(env_path,allow_pickle=True).item()



        modal_path = {'gph':r'G:\data\AAAI_data\geopotential_500_year_centercrop',
                      'mcc':'/home/hc/Desktop/hca6000/TYDataset/wind_year_MCC_centercrop',
                      '10v':'/home/hc/Desktop/hca6000/TYDataset/wind_year_V10_centercrop',
                      '10u':'/home/hc/Desktop/hca6000/TYDataset/wind_year_U10_centercrop',
                      'sst':'/home/hc/Desktop/hca6000/TYDataset/SST_year_centercrop',
                      '100v': '/home/hc/Desktop/hca6000/TYDataset/wind_year_V100_centercrop',
                      '100u': '/home/hc/Desktop/hca6000/TYDataset/wind_year_U100_centercrop',
                      }
        data_dir = os.path.join(modal_path[self.modal_name], year, tyname)
        image_obs = []
        image_pre = []
        obs_list = tydate[:self.obs_len]
        pre_list = tydate[self.obs_len:]
        for obs_date in obs_list:
            img_path = os.path.join(data_dir, obs_date + '.npy')
            img = self.img_read(img_path)
            image_obs.append(img)
        for pre_date in pre_list:
            img_path = os.path.join(data_dir, pre_date + '.npy')
            img = self.img_read(img_path)
            image_pre.append(img)
        image_obs = torch.tensor(np.array(image_obs), dtype=torch.float)
        image_pre = torch.tensor(np.array(image_pre), dtype=torch.float)
        return {'obs': image_obs, 'pre': image_pre,'env':env_data}

    def __getitem__(self, index):
        # 迭代一次获取一个子序列的所有行人的轨迹，台风的话只有一个轨迹.
        # 这里的子轨迹只有20点，8或12作为先决条件，这样的话，就有一个假设就是：
        # 当前时刻的    将来轨迹只与近8或者12个点信息有关
        start, end = self.seq_start_end[index]
        image = self.get_img(self.tyID[start:end][0])
        out = [
            self.obs_traj[start:end, :], self.pred_traj[start:end, :],
            self.obs_traj_rel[start:end, :], self.pred_traj_rel[start:end, :],
            self.non_linear_ped[start:end], self.loss_mask[start:end, :],
            self.obs_traj_Me[start:end,:],self.pred_traj_Me[start:end,:],
            self.obs_traj_rel_Me[start:end, :], self.pred_traj_rel_Me[start:end, :],
            self.obs_date_mask[start:end, :],self.pred_date_mask[start:end, :],
            image['obs'],image['pre'],image['env'],
            self.tyID[start:end]
        ]
        return out


if __name__ == '__main__':
    path = r'/data/hc/MMSTN_prior_unet_variant/MMSTN_multige_prior_unet_flexible/datasets/1950_2019/test'
    dset = TrajectoryDataset(path,obs_len=8,pred_len=4,skip=1,delim='\t')
    loader = DataLoader(dset,batch_size=16,shuffle=True,num_workers=4,collate_fn=seq_collate)
    for batch in loader:
        # pass
        g_index = {'01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 1, '07': 2, '08': 2, '09': 2, '10': 1, '11': 0,
                   '12': 0, }
        month_list = [g_index[batch[-1][i][0]['new'][0][4:6]] for i in range(len(batch[-1]))]
        print(batch[-1])
        image_obs = batch[-4]
        image_pre = batch[-3]
        env_data = batch[-2]
        print(image_obs.shape)
        print(image_pre.shape)
        for x in env_data:
            print(x,env_data[x].shape)
        # print(env_data)
