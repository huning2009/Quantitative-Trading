import datetime
import numpy as np


def get_time(t):
    time = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
    minus_9_30 = (int(time.strftime('%H')) - 9) * 12 + int(time.strftime('%M')) / 5 - 6
    return minus_9_30 if minus_9_30 < 25 else minus_9_30 - 18


class Actions:
    dim = 3
    
    def __init__(self, action_prob):
        # 买、卖、持有的几率
        self.p_buy = action_prob[0]
        self.p_sell = action_prob[1]
        self.p_hold = 1 - action_prob[0] - action_prob[1]
        
        self.action_choose = np.random.choice(['buy', 'sell', 'hold'],
                                              p=[self.p_buy, self.p_sell, self.p_hold])
# Deubg
#         print('action_prob: {}, action is {}'.format(action_prob, self.action_choose))
    
    def choose(self):
        return self.action_choose


class Observations:
    def __init__(self, index, is_hold, wait_time, trade_price):
        # 历史数据从 index 开始
        # is_hold: 是否持有股票，1表示持有，0表示未持有
        # trade_price: 距离上次操作的时间（多少个5分钟）
        # trade_price: 上次交易价格
        
        self.index = index
        self.is_hold = is_hold
        self.wait_time = wait_time
        self.trade_price = trade_price
    
    def values(self, history_data, length):
        # history_data: DataFram 索引越靠前日期越靠前
        # 其中 time 为 0 到 48， 表示一天中的第几个5分钟
        # 最后三位分别是 is_hold * 100，即100为持仓, 持仓是否过夜，100为过夜
        
        feature = [x for x in history_data.columns if x.startswith('norm')]
        recent_data = history_data[feature][self.index: self.index + length]
        # recent_data['vol'] = recent_data['vol']/10000
        # recent_data['trade_time'] = recent_data['trade_time'].apply(lambda x: get_time(x))
        # is_pass_night = self.wait_time > 48 or self.wait_time > recent_data['trade_time'].iloc[0]
        values = np.array(recent_data.values)   # .reshape(1, -1)
        # print('length: ', history_data.shape[0])
        # print(self.index + length - 1)
        # print(values)
        # print('1: ', values[0][self.index])
        # print('2: ', values[0][values[0][self.index + length - 1]])
        # for i in range(0, length-1):
        #     values[0][i] = 100 * (values[0][i] - values[0][i+1]) / values[0][i+1]
            
        return values
        # return np.hstack([np.array(recent_data.values).reshape(1, -1),
        #                   np.array([[self.is_hold * 100, 100 if is_pass_night else 0, self.trade_price]])])
    
    def decode(self, history_data, length, log=False):
        recent_data = history_data[['trade_time', 'open', 'high', 'low', 'close', 'vol']].iloc[
                      self.index: self.index + length]
        
        recent_data['trade_time'] = recent_data['trade_time'].apply(lambda x: get_time(x))

        if log:
            print('recent data is :\n', recent_data)
            print('')

            if self.is_hold:
                print('Hold stock for {} minutes， purchase price is {}.'.format(
                    self.wait_time * 5, self.trade_price))
            else:
                print('Dosen\'t hold any thing.')
        return recent_data
    
    def __str__(self):
        return 'index: {}, is_hold: {}, wait_time: {}, trade_price: {}\n'.format(
            self.index, self.is_hold, self.wait_time, self.trade_price)
    
    def __repr__(self):
        return self.__str__()


def calc_reward_batch(obs, next_obs, history_data):
    # obs 和 next_obs 为 Observation 类
    
    fee = next_obs.trade_price * 0.02 if next_obs.wait_time == 1 else 0
    if obs.is_hold == 1:
        delta_price = (history_data['close'].iloc[next_obs.index]
                       - history_data['close'].iloc[obs.index]) * 100
 
        return delta_price - fee
    else:
        return -fee


# 可能有问题，由于数据倒序了，前面的数据日期早
class Env:
    def __init__(self, hps, data_set):
        self._hps = hps
        self._history_data = data_set.history_data
        self._reset_obs = Observations(index=0, is_hold=0, wait_time=0, trade_price=0)
        
        self._observations_dim = self._reset_obs.values(data_set.history_data, hps.encode_step).shape[1]
        self._actions_dim = Actions.dim
        return
    
    def reset(self):
        return self._reset_obs
    
    def step(self, obs, action):
        # 输入为 Observations 类和 Actions 类
        # 返回值为 next observations， reward， done
        index, is_hold, wait_time, trade_price = obs.index, obs.is_hold, obs.wait_time, obs.trade_price
        done = True if index == self._hps.train_data_num-1 else False
        action_choose = action.choose()
        
        if is_hold == 1 and action_choose == 'sell':
            current_time = get_time(self._history_data['trade_time'].iloc[index])
            is_pass_night = wait_time > 48 or wait_time > current_time
            if is_pass_night:
                is_hold = 0  # 卖掉了
                wait_time = 0  # 时间清0
                trade_price = self._history_data['close'].iloc[index]  # 以当前的收盘价为成交加个
            else:
                pass  # 不做操作，类似 hold
        elif is_hold == 0 and action_choose == 'buy':
            is_hold = 1
            wait_time = 0
            trade_price = self._history_data['close'].iloc[index]
        else:
            pass  # 不做操作
        
        next_obs = Observations(index + 1, is_hold, wait_time + 1, trade_price)
        return next_obs, calc_reward_batch(obs, next_obs, self._history_data), done
    
    @property
    def observations_dim(self):
        return self._observations_dim
    
    @property
    def actions_dim(self):
        return self._actions_dim


def main():
    from data_set import DataSet
    from collections import namedtuple
    hps = {
        'encode_step': 5,  # 历史数据个数
        'train_data_num': 100000,  # 训练集个数
        }
    
    hps = namedtuple("HParams", hps.keys())(**hps)
    
    data_set = DataSet(hps)
    obs = Observations(0, 0, 0, 0)
    print(obs.values(data_set.history_data, hps.encode_step).shape)
    return


if __name__ == '__main__':
    np.set_printoptions(2)
    main()
