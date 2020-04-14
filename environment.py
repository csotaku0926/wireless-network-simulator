import UserEquipment as ue
import LTEBaseStation as LTEbs
import NRBaseStation as NRbs
import Satellite as SATbs
import util
from concurrent.futures import ThreadPoolExecutor
import math
import random


class wireless_environment:
    bs_list = []
    ue_list = []
    x_limit = None
    y_limit = None
    env_type = util.EnvType.URBAN

    def __init__(self, n, m = None):
        if m is not None:
            self.y_limit = m
        else:
            self.y_limit = n
        self.x_limit = n
    
    def insert_ue(self, requested_bitrate, starting_position = None, speed = 0, direction = 0):
        if starting_position is not None and (starting_position[2] > 10 or starting_position[2] < 1):
            raise Exception("COST-HATA model requires UE height in [1,10]m")
        
        ue_id = -1
        
        if None in self.ue_list:
            ue_id = self.ue_list.index(None)
        else:
            ue_id = len(self.ue_list)
        
        if starting_position is None:
            new_ue = ue.user_equipment(requested_bitrate, ue_id, (random.randint(0, self.x_limit),random.randint(0, self.y_limit),1), self, speed, direction)
        else: 
            new_ue = ue.user_equipment(requested_bitrate, ue_id, starting_position, self, speed, direction)
        
        if (ue_id == len(self.ue_list)):
            self.ue_list.append(new_ue)
        else:
            self.ue_list[ue_id] = new_ue
        return new_ue.ue_id
    

    def remove_ue(self, ue_id):
        self.ue_list[ue_id] = None

    
    def place_SAT_base_station(self, position):       
        new_bs = SATbs.Satellite(len(self.bs_list), position, self)
        
        self.bs_list.append(new_bs)
        return new_bs.bs_id

    def place_LTE_base_station(self, position, carrier_frequency, antenna_power, antenna_gain, feeder_loss, available_bandwidth):
        
        if (available_bandwidth in LTEbs.LTEbandwidth_prb_lookup):
            #  LTE standard defines 12 subcarriers of 15KHz each, so the pbr_bandwidth is 180KHz
            #  LTEbandwidth_prb_lookup defines the number of blocks of 180KHz available in the specified bandwidth,
            #  so we have to multiply by the number of time slots (sub-frames in LTE terminoloty) in a time frame
            new_bs = LTEbs.LTEBaseStation(len(self.bs_list), LTEbs.LTEbandwidth_prb_lookup[available_bandwidth]*10, 180, 12, antenna_power, antenna_gain, feeder_loss, carrier_frequency, position, self)
        else:
            raise Exception("if you indicate the available bandwidth, it must be 1.4, 3, 5, 10, 15 or 20 MHz")
        
        self.bs_list.append(new_bs)
        return new_bs.bs_id
    
    def place_NR_base_station(self, position, carrier_frequency, numerology, antenna_power, antenna_gain, feeder_loss, available_bandwidth):
        #check if the bandwith is in line with the specified numerology and specified carrier frequency
        fr = -1
        if (carrier_frequency <= 6000):  #below 6GHz
            fr = 0
        elif (carrier_frequency >= 24250 and carrier_frequency <= 52600): #between 24.25GHz and 52.6GHz
            fr = 1
        else:
            raise Exception("NR frequency outside admissible ranges")

        if available_bandwidth in NRbs.NRbandwidth_prb_lookup[numerology][fr]:
            prb_size = 15*(2**numerology)*12 #15KHz*12subcarriers for numerology 0, 30KHz*12subcarriers for numerology 1, etc.
            #  NRbandwidth_prb_lookup defines the number of blocks of 180KHz available in the specified bandwidth with a certain numerology,
            #  so we have to multiply by the number of time slots (sub-frames in LTE terminology) in a time frame
            new_bs = NRbs.NRBaseStation(len(self.bs_list), NRbs.NRbandwidth_prb_lookup[numerology][fr][available_bandwidth] * (10 * 2**numerology), prb_size, 12, numerology, antenna_power, antenna_gain, feeder_loss, carrier_frequency, position, self)
        else:
            raise Exception("The choosen bandwidth is not present in 5G NR standard with such numerology and frequency range")

        self.bs_list.append(new_bs)
        return new_bs.bs_id



    
    #this method shall be called by an UE 
    #that wants to have a measure of the RSRP 
    #associated to each BS
    def discover_bs(self, ue_id):
       thread_pool = []
       #rsrp = [None]*len(self.bs_list)
       rsrp = dict()
       with ThreadPoolExecutor(max_workers=len(self.bs_list)) as executor:
            for i in range(0, len(self.bs_list)):
                thread = executor.submit(util.compute_rsrp, self.ue_list[ue_id], self.bs_list[i], self)
                thread_pool.append(thread)
            for i in range(0, len(self.bs_list)):
                res = thread_pool[i].result() 
                if (res > util.MIN_RSRP):
                    rsrp[i] = res
       return rsrp

    def next_timestep(self):
        with ThreadPoolExecutor(max_workers=len(self.ue_list)) as executor:
            for ue in self.ue_list:
                thread = executor.submit(ue.next_timestep())
        for bs in self.bs_list:
            bs.next_timestep()
       


