'''
This housekeeping script reads a ROOT file, opens a TTree whose name is specified
by the user, and produces a dictionary that has the structure of
<key> = 'name of branch' and <value> = 'branch description'.
'''
from ROOT import TFile, TTree, TBranch
import json

def get_branch_name_description(filename, treename):
    branches = dict()
    myfile = TFile.Open(filename, 'READ')
    trees = myfile.Get(treename)
    brlist = trees.GetListOfBranches()
    for br in brlist:
        branches[br.GetName()] = br.GetTitle()
    return branches

def make_json(stuff):
    json_str = json.dumps(stuff, indent=4)
    return json_str

if __name__=='__main__':
    mcbkg = '/data/submit/kyoon/D04/BToJpsi_JPsiToMuMu_BMuonFilter_HardQCD_TuneCP5_13TeV-pythia8-evtgen+RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v1+MINIAODSIM/00573B89-23D5-2347-8CF2-6B9DA7D2A469.root'
    databkg = '/scratch/submit/cms/mariadlf/Hrare/newSKIMS/D04/BPH/2018/Charmonium+RunA/output_CharmoniumA_2018_0.root'
    mcsig = '/data/submit/cms/store/user/mariadlf/nano/GluGluH_HJPsiCC/NANOAOD_D04/nano_GluGluH_HJPsiCC_1.root'
    my_json_dict = dict()
    my_json_dict['MC_BKG'] = {'Events': get_branch_name_description(mcbkg, 'Events'), 'Runs': get_branch_name_description(mcbkg, 'Runs')}
    my_json_dict['DATA_BKG'] = {'Events': get_branch_name_description(databkg, 'Events')}
    my_json_dict['MC_SIG'] = {'Events': get_branch_name_description(mcsig, 'Events'), 'Runs': get_branch_name_description(mcsig, 'Runs')}
    json_str = make_json(my_json_dict)
    print(json_str)