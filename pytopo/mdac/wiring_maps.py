#Create mapping between MDAC channels and microD cable lines.  In other words, the key represents the line at the top of the fridge 
#and the value represents the corresponding MDAC channel.
def fridge_BoB_to_mdac(mdac1, mdac2):
    #Names of breakout-box (BoB) channels in format box#-pin#
    mdac1_BoB_list = ['1-1', '1-2', '1-3', '1-4', '1-5', '1-6', '1-7', '1-8', '1-9', '1-10', '1-11', '1-12',
                      '1-13', '1-14', '1-15', '1-16', '1-17', '1-18', '1-19', '1-20', '1-21', '1-22', '1-23', '1-24', '1-25',
                      '2-1', '2-2', '2-3', '2-4', '2-5', '2-6', '2-7', '2-8', '2-9', '2-10', '2-11', '2-12',
                      '2-13', '2-14', '2-15', '2-16', '2-17', '2-18', '2-19', '2-20', '2-21', '2-22', '2-23', '2-24', '2-25']

    mdac2_BoB_list = ['3-1', '3-2', '3-3', '3-4', '3-5', '3-6', '3-7', '3-8', '3-9', '3-10', '3-11', '3-12',
                      '3-13', '3-14', '3-15', '3-16', '3-17', '3-18', '3-19', '3-20', '3-21', '3-22', '3-23', '3-24', '3-25',
                      '4-1', '4-2', '4-3', '4-4', '4-5', '4-6', '4-7', '4-8', '4-9', '4-10', '4-11', '4-12',
                      '4-13', '4-14', '4-15', '4-16', '4-17', '4-18', '4-19', '4-20', '4-21', '4-22', '4-23', '4-24', '4-25']

    
    i = 0
    for BoB_ch in mdac1_BoB_list:
        if BoB_ch == '1-1':
            fridge_BoB_to_mdac_dict = {BoB_ch: mdac1[i]}
        else:
            if BoB_ch.startswith('1'):
                if BoB_ch == '1-13':
                    pass
                else:
                    if BoB_ch == '1-25':
                        fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[12]
                    else:
                        fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[i]
            else:
                if BoB_ch == '2-13':
                    pass
                else:
                    if BoB_ch == '2-25':
                        fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[36]
                    else:
                        fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[i-1]            
                                            
        i += 1  

    i = 0
    for BoB_ch in mdac2_BoB_list:
        if BoB_ch.startswith('3'):
            if BoB_ch == '3-13':
                pass 
            else:
                if BoB_ch == '3-25':
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[12]
                else:
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[i]
        else:
            if BoB_ch == '4-13':
                pass 
            else:
                if BoB_ch == '4-25':
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[36]
                else:
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[i-1]            
                                            
        i += 1  
    
    
    
    return fridge_BoB_to_mdac_dict

def fridge_BoB_to_mdac_v1_2(mdac1, mdac2):
    #Names of breakout-box (BoB) channels in format box#-pin#
    mdac1_BoB_list = ['1-1', '1-2', '1-3', '1-4', '1-5', '1-6', '1-7', '1-8', '1-9', '1-10', '1-11', '1-12',
                      '1-13', '1-14', '1-15', '1-16', '1-17', '1-18', '1-19', '1-20', '1-21', '1-22', '1-23', '1-24', '1-25',
                      '2-1', '2-2', '2-3', '2-4', '2-5', '2-6', '2-7', '2-8', '2-9', '2-10', '2-11', '2-12',
                      '2-13', '2-14', '2-15', '2-16', '2-17', '2-18', '2-19', '2-20', '2-21', '2-22', '2-23', '2-24', '2-25']

    mdac2_BoB_list = ['3-1', '3-2', '3-3', '3-4', '3-5', '3-6', '3-7', '3-8', '3-9', '3-10', '3-11', '3-12',
                      '3-13', '3-14', '3-15', '3-16', '3-17', '3-18', '3-19', '3-20', '3-21', '3-22', '3-23', '3-24', '3-25',
                      '4-1', '4-2', '4-3', '4-4', '4-5', '4-6', '4-7', '4-8', '4-9', '4-10', '4-11', '4-12',
                      '4-13', '4-14', '4-15', '4-16', '4-17', '4-18', '4-19', '4-20', '4-21', '4-22', '4-23', '4-24', '4-25']

    
    i = 0
    for BoB_ch in mdac1_BoB_list:
        if BoB_ch == '1-1':
            fridge_BoB_to_mdac_dict = {BoB_ch: mdac1[i]}
        else:
            if BoB_ch.startswith('1'):
                if BoB_ch == '1-13':
                    pass
                else:
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[i]
            else:
                if BoB_ch == '2-13':
                    pass
                else:
                    fridge_BoB_to_mdac_dict[BoB_ch] = mdac1[i]            
                                            
        i += 1  


    i = 0
    for BoB_ch in mdac2_BoB_list:
        if BoB_ch.startswith('3'):
            if BoB_ch == '3-13':
                pass 
            else:
                fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[i]
        else:
            if BoB_ch == '4-13':
                pass 
            else:
                fridge_BoB_to_mdac_dict[BoB_ch] = mdac2[i]            
                                            
        i += 1  
    
    
    
    return fridge_BoB_to_mdac_dict

#Mapping of fridge pin to probe pin.  In other words, for a given PCB bondpad the key represents the line at the 
#top of the fridge and the corresponding item represents the pin on the probe.
def fridge_to_probe_map():
    fridge_to_probe = {'3-9': '2-17',
                       '3-21': '2-5',
                       '3-8': '2-18',
                       '3-20': '2-6',
                       '3-19': '2-7',
                       '3-18': '2-8',
                       '3-17': '2-22',
                       '3-4': '2-9',
                       '3-3': '2-23',
                       '4-16': '1-10',
                       '3-15': '2-11',
                       '3-25': '2-1',
                       '3-12': '2-14',
                       '1-1': '4-25',
                       '1-14': '4-12',
                       '2-17': '3-9',
                       '2-5': '3-21',
                       '2-18': '3-8',
                       '2-6': '3-20',
                       '2-7': '3-19',
                       '2-8': '3-18',
                       '2-9': '3-17',
                       '2-22': '3-4',
                       '2-23': '3-3',
                       '1-10': '4-16',
                       '2-11': '3-15',
                       '2-1': '3-25',
                       '2-14': '3-12',
                       '4-25': '1-1',
                       '4-12': '1-14',
                       '4-24': '1-2',
                       '3-10': '2-16',
                       '3-22': '2-4',
                       '4-9': '1-17',
                       '4-20': '1-6',
                       '3-7': '2-19',
                       '3-6': '2-20',
                       '3-5': '2-21',
                       '4-5': '1-21',
                       '3-16': '2-10',
                       '3-2': '2-24',
                       '3-14': '2-12',
                       '4-1': '1-25',
                       '3-1': '2-25',
                       '2-2': '3-24',
                       '2-15': '3-11',
                       '2-3': '3-23',
                       '1-2': '4-24',
                       '2-16': '3-10',
                       '2-4': '3-22',
                       '1-17': '4-9',
                       '1-6': '4-20',
                       '2-19': '3-7',
                       '2-20': '3-6',
                       '2-21': '3-5',
                       '1-21': '4-5',
                       '2-10': '3-16',
                       '2-24': '3-2',
                       '2-12': '3-14',
                       '1-25': '4-1',
                       '2-25': '3-1',
                       '3-24': '2-2',
                       '3-11': '2-15',
                       '3-23': '2-3',
                       '4-22': '1-4',
                       '4-10': '1-16',
                       '4-21': '1-5',
                       '4-8': '1-18',
                       '4-7': '1-19',
                       '4-19': '1-7',
                       '4-6': '1-20',
                       '4-18': '1-8',
                       '4-17': '1-9',
                       '4-4': '1-22',
                       '4-15': '1-11',
                       '4-3': '1-23',
                       '4-2': '1-24',
                       '4-14': '1-12',
                       '1-15': '4-11',
                       '1-3': '4-23',
                       '1-4': '4-22',
                       '1-16': '4-10',
                       '1-5': '4-21',
                       '1-18': '4-8',
                       '1-19': '4-7',
                       '1-7': '4-19',
                       '1-20': '4-6',
                       '1-8': '4-18',
                       '1-9': '4-17',
                       '1-22': '4-4',
                       '1-11': '4-15',
                       '1-23': '4-3',
                       '1-24': '4-2',
                       '1-12': '4-14',
                       '4-11': '1-15',
                       '4-23': '1-3'
                      }
    return fridge_to_probe



def channel_mapper(fridge_pin, mdac1, mdac2, probe_connection=False):    
    # fridge_to_probe_dict = fridge_to_probe_map()
    
    if not(probe_connection):
        channel = fridge_BoB_to_mdac(mdac1, mdac2)[fridge_pin]
    else:
        channel = fridge_BoB_to_mdac(mdac1, mdac2)[fridge_to_probe_map()[fridge_pin]]
    return channel

mdac1 = list(range(1,65))
mdac2 = list(range(65,128))

#print(fridge_BoB_to_mdac(mdac1, mdac2))
wiring_dict = fridge_BoB_to_mdac(mdac1, mdac2)

print(wiring_dict['3-3'])

