'''
rdfdefines
+++++++++++++++++++++++++++++++++++++++++++++

Library of definitions that contain analysis category-specific RDF defines and filters.
'''
from kytools import jsonreader
import ROOT, os
from datetime import datetime

ROOT.EnableImplicitMT

def filter_rdf(rdf, cut_flow_dict, cut, description, filter=True):
    '''Filter an RDF.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
        cut (str): The filter expression.
        description (str): The description of this filter.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified RDF.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    new_rdf = rdf.Filter(cut, description) if filter else rdf
    if filter: cut_flow_dict = add_cut_flow(cut_flow_dict, cut, new_rdf.Sum('w').GetValue())
    return new_rdf, cut_flow_dict

def load_functions(mode='reco'):
    '''Load user-defined functions.

    Args:
        mode (str, optional): Mode of loading.
            Options are 'reco' and 'gen'.

    Returns:
        (None)
    '''
    match mode:
        case 'reco':
            ROOT.gSystem.CompileMacro(os.path.join(os.environ['HRARE_DIR'], 'JPsiCC', 'src', 'functions.cc'), 'k')
        case 'gen':
            ROOT.gSystem.CompileMacro(os.path.join(os.environ['HRARE_DIR'], 'JPsiCC', 'src', 'GenAnalyzer.cc'), 'k')

def add_cut_flow(cut_flow_dict, cut_str, cut_nentries):
    '''Add the cut flow str and value to the dictionary containing the cut flow.

    Each cut_str is modified so that the Nth entry will have a prefix 'N.'.

    Args:
        cut_flow_dict (dict(str: float)): The dictionary containing the cut flow.
        cut_str (str): The string describing the cut.
        cut_nentries (int or float): The number of entries after the cut.

    Returns:
        cut_flow_dict (dict(str: float)): Updated dictionary.

    Raises:
        TypeError: If cut_str is not str.
        TypeError: If cut_netries is not numerical.
    '''
    if not isinstance(cut_str, str): raise TypeError('cut_str must be str.')
    if not isinstance(cut_nentries, (int, float)): raise TypeError('cut_nentries must be numerical.')
    nth_entry = len(cut_flow_dict)
    cut_flow_dict[f'#{nth_entry} {cut_str}'] = float(cut_nentries)
    return cut_flow_dict

def get_rdf_branches(key):
    '''Get RDF branches to snapshot for a specific key in rdf_hists.json.

    Args:
        key (str): Key to the histogram definitions in the json file.

    Returns:
        branchlist (str): List of RDF branches in the histogram definitions.
    '''
    hist_defs = jsonreader.get_object_from_json(anpath='JPsiCC',
                                                    jsonname='rdf_hists.json',
                                                    keys=['NANOAOD_to_RDF'])
    branchlist = []
    for _, hdef in hist_defs[key].items():
        branchlist.append(hdef['name'])
    return branchlist

def compute_sum_weights(rdf_runs, sample_name):
    '''Compute the weights.

    Only works if the RDF has columns named 'genEventSumw' and 'genEventCount'.

    Args:
        rdf_runs (ROOT.RDataFrame): ROOT.RDataFrame object created from the 'Runs' tree.
        sample_name (str): Name of the sample.

    Returns:
        gen_event_sumw (float): Sum of 'genEventSumw' column values.
        gen_event_count (float): Sum of 'genEventCount' column values.
    '''
    gen_event_sumw = rdf_runs.Filter(f'sample=="{sample_name}"').Sum('genEventSumw').GetValue()
    gen_event_count = rdf_runs.Filter(f'sample=="{sample_name}"').Sum('genEventCount').GetValue()
    if not gen_event_count == gen_event_sumw:
        print('WARNING in compute_sum_weights:\ngen_event_sumw not equal to gen_events_count')
        print(f'gen_event_sumw: {gen_event_sumw}, gen_event_count: {gen_event_count}')
    return gen_event_sumw, gen_event_count

def rdf_def_sample_meta(rdf_events, branches=[]):
    '''RDF define columns pertinent to the meta information.

    Args:
        rdf_events (ROOT.RDataFrame): The RDataFrame object created from the 'Events' tree
            from a JSON specification file.
        branches (list(str), optional): List of TBranches.
            Defaults to [].

    Returns:
        new_rdf (ROOT.RDataFrame): Modified RDataFrame.
        branches (list(str)): Updated list of TBranches.
    '''
    new_rdf = (rdf_events.DefinePerSample('sample', 'rdfsampleinfo_.GetSampleName()')
                        .DefinePerSample('sample_category', 'rdfsampleinfo_.GetS("sample_category")')
                        .DefinePerSample('xsec', 'rdfsampleinfo_.GetD("xsec")')
                        .DefinePerSample('lumi', 'rdfsampleinfo_.GetD("lumi")')
    )
    branches += ['sample', 'sample_category', 'xsec', 'lumi']
    return new_rdf, branches

def rdf_def_weights(rdf_runs, rdf_events, branches=[], cut_flow_dict={}, data=False):
    '''RDF define a column with weights.

    Args:
        rdf_runs (ROOT.RDataFrame): ROOT.RDataFrame object created from the 'Runs' tree.
            Only works if the RDF has columns named 'genEventSumw' and 'genEventCount'.
            Can be (None) if data=True.
        rdf_events (ROOT.RDataFrame): The ROOT.RDataFrame object created from the 'Events' tree.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        data (bool, optional): Whether the provided RDF is data.
            Defaults to False.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    hash = datetime.now().strftime("%H%M%S%f")
    if not data:
        sample_col =rdf_events.Take['string']('sample')
        sample_names = list(set(sample_col.GetValue()))
        list_sum_weights = []
        for sname in sample_names:
            list_sum_weights.append((sname, compute_sum_weights(rdf_runs, sname)))
        func_sum_weights = f'float func_sum_weights_{hash}(unsigned int slot, const ROOT::RDF::RSampleInfo &id) {{\n'
        max_idx = len(list_sum_weights)
        for idx in range(max_idx):
            item = list_sum_weights[idx]
            if idx == 0:
                func_sum_weights += f'  if (id.Contains("{item[0]}")) {{return {item[1][0]};}}\n'
            else:
                func_sum_weights += f'  else if (id.Contains("{item[0]}")) {{return {item[1][0]};}}\n'
        func_sum_weights += f'  else {{return 1.;}}\n}}'
        weight_exp = 'xsec*genWeight*lumi/sum_weights'
    else:
        weight_exp = '1.0'
        func_sum_weights = f'float func_sum_weights_{hash}(unsigned int slot, const ROOT::RDF::RSampleInfo &id) {{return 1.;}}'
    ROOT.gInterpreter.Declare(func_sum_weights)
    new_rdf = (rdf_events.DefinePerSample('sum_weights', f'func_sum_weights_{hash}(rdfslot_, rdfsampleinfo_)')
                        .Define('w', weight_exp)
    )
    cut_flow_dict = add_cut_flow(cut_flow_dict, 'w', new_rdf.Sum('w').GetValue())
    branches += ['sum_weights', 'w']
    if not data: branches.append('genWeight')
    return new_rdf, branches, cut_flow_dict

def rdf_def_triggers(rdf, CAT, YEAR, branches=[], cut_flow_dict={}, filter=True):
    '''RDF define and filter with triggers.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        CAT (str): Analysis category.
        YEAR (int): Year of data-taking.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        filter (bool, optional): Whether to filter.
            Defaults to True.        

    Returns:
        new_rdf (ROOT.RDataFrame): Modified RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.

    Raises:
        ValueError: If the combination of 'CAT' and 'YEAR' does not correspond
            to an existing trigger.
    '''
    match f'{CAT}_{YEAR}':
        case 'GF_2018':
            # trigger = '(HLT_Dimuon20_Jpsi_Barrel_Seagulls || HLT_Dimuon25_Jpsi)'
            trigger = 'HLT_Dimuon25_Jpsi'
            print(f'The following triggers are applied: {trigger}')
        case _:
            raise ValueError(f'Trigger does not exist for the combination of {CAT} and {YEAR}.')
    try:
        new_rdf = rdf.Define('trigger', trigger)
        if filter:
            new_rdf = new_rdf.Filter('trigger>0')
            cut_flow_dict = add_cut_flow(cut_flow_dict, 'trigger', new_rdf.Sum('w').GetValue())
        branches += ['trigger']
    except Exception:
        new_rdf = rdf.Define('trigger_user', trigger)
        print('WARNING: a column named \'trigger\' could not be defined, so it is renamed to \'trigger_user\' instead.')
        if filter:
            new_rdf = new_rdf.Filter('trigger_user>0')
            cut_flow_dict = add_cut_flow(cut_flow_dict, 'trigger_user', new_rdf.Sum('w').GetValue())
        branches += ['trigger', 'trigger_user']
    return new_rdf, branches, cut_flow_dict

def rdf_def_jpsi(rdf, branches=[], cut_flow_dict={}, filter=True):
    '''RDF definition for J/Psi.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified ROOT.RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    load_functions('reco')
    new_rdf, cut_flow_dict = filter_rdf(rdf, cut_flow_dict, 'nJpsi>0', 'Event must contain at least one J/psi with the given purity criteria.', filter=filter)
    new_rdf = new_rdf.Define('Jpsi_muon1_muon2_dR', 'deltaR(Jpsi_muon1_eta[0], Jpsi_muon1_phi[0], Jpsi_muon2_eta[0], Jpsi_muon2_phi[0])')
    branches += get_rdf_branches('Jpsi')
    return new_rdf, branches, cut_flow_dict

def rdf_def_muons(rdf, branches=[], cut_flow_dict={}, filter=True):
    '''Muons RDF definition.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified ROOT.RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    new_rdf = rdf
    branches += get_rdf_branches('muon')
    return new_rdf, branches, cut_flow_dict

def rdf_def_vertex(rdf, branches=[], cut_flow_dict={}, filter=True):
    '''Vertex RDF definition.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified ROOT.RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    if filter: new_rdf = rdf.Filter('PV_npvsGood>0', 'Number of PVs must be at least 1.')
    else: new_rdf = rdf
    cut_flow_dict = add_cut_flow(cut_flow_dict, 'PV_npvsGood>0', new_rdf.Sum('w').GetValue())
    branches += get_rdf_branches('vertex')
    return new_rdf, branches, cut_flow_dict

def rdf_def_jets(rdf, CAT, YEAR, branches=[], cut_flow_dict={}, data=False, filter=True):
    '''Jets RDF definition.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        CAT (str): Analysis category.
        YEAR (int): Year of data-taking.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        data (bool, optional): Whether the provided RDF is data.
            Defaults to False.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified ROOT.RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.

    Raises:
        ValueError: If the combination of 'CAT' and 'YEAR' does not correspond
            to an existing trigger.
    '''
    load_functions('reco')
    match f'{CAT}_{YEAR}':
        case 'GF_2018':
            goodjets = '(Jet_pt > 30 && abs(Jet_eta) < 2.5 && Jet_btagDeepCvL > -1)'
        case _:
            raise ValueError(f'Good-jets definition does not exist for the combination of {CAT} and {YEAR}.')
    new_rdf = (rdf.Define('goodJets', goodjets)
                .Define('nGoodJets', 'Sum(goodJets)')
    )
    if filter:
        new_rdf = new_rdf.Filter('nGoodJets>=2', 'Events must contain two jets from the charm quarks.')
        cut_flow_dict = add_cut_flow(cut_flow_dict, 'nGoodJets>=2', new_rdf.Sum('w').GetValue())
    new_rdf = (new_rdf.Define('goodJetPt', 'Jet_pt[goodJets]')
                .Define('goodJetEta', 'Jet_eta[goodJets]')
                .Define('goodJetPhi', 'Jet_phi[goodJets]')
                .Define('goodJetMass', 'Jet_mass[goodJets]')
                .Define('goodJetCvL', 'Jet_btagDeepCvL[goodJets]')
    )
    new_rdf = (new_rdf.Define('jet1_pt', 'goodJetPt[0]')
                .Define('jet2_pt', 'goodJetPt[1]')
                .Define('jet1_eta', 'goodJetEta[0]')
                .Define('jet2_eta', 'goodJetEta[1]')
                .Define('jet1_phi', 'goodJetPhi[0]')
                .Define('jet2_phi', 'goodJetPhi[1]')
                .Define('jet1_mass', 'goodJetMass[0]')
                .Define('jet2_mass', 'goodJetMass[1]')
                .Define('jet1_CvL', 'goodJetCvL[0]')
                .Define('jet2_CvL', 'goodJetCvL[1]')
                .Define('index_CloseFar', 'jetCloseFar(goodJetPt, goodJetEta, goodJetPhi, goodJetMass,'
                                        'Jpsi_kin_pt, Jpsi_kin_eta, Jpsi_kin_phi, Jpsi_kin_mass)')
    )
    if filter:
        new_rdf = new_rdf.Filter('index_CloseFar[0]!= -1', 'at least one close jet')
        cut_flow_dict = add_cut_flow(cut_flow_dict, 'nCloseJets>0', new_rdf.Sum('w').GetValue())
    new_rdf = (new_rdf.Define('jetClose_nMuons','Jet_nMuons[goodJets][index_CloseFar[0]]')
                .Define('jetFar_nMuons','Jet_nMuons[goodJets][index_CloseFar[1]]')
                .Define('jetClose_nElectrons','Jet_nElectrons[goodJets][index_CloseFar[0]]')
                .Define('jetFar_nElectrons','Jet_nElectrons[goodJets][index_CloseFar[1]]')
                .Define('jetClose_pt','goodJetPt[index_CloseFar[0]]')
                .Define('jetFar_pt','goodJetPt[index_CloseFar[1]]')
                .Define('jetClose_cRegCorr','Jet_cRegCorr[goodJets][index_CloseFar[0]]')
                .Define('jetFar_cRegCorr','Jet_cRegCorr[goodJets][index_CloseFar[1]]')
                .Define('jetClose_CvL','goodJetCvL[index_CloseFar[0]]')
                .Define('jetFar_CvL','goodJetCvL[index_CloseFar[1]]')
                .Define('jetClose_nConst','Jet_nConstituents[goodJets][index_CloseFar[0]]')
                .Define('jetFar_nConst','Jet_nConstituents[goodJets][index_CloseFar[1]]')
                .Define('jetClose_JpsiPtRatio','Jpsi_kin_pt[0]/goodJetPt[index_CloseFar[0]]')
    )
    branches += ['goodJets', 'nGoodJets', 'goodJetPt', 'goodJetEta', 'goodJetPhi', 'goodJetMass', 'goodJetCvL']
    branches += get_rdf_branches('jet')
    if not data:
        new_rdf = (new_rdf.Define('goodPartonFlavour', 'Jet_partonFlavour[goodJets]')
                    .Define('jet1_partonFlavour', 'abs(goodPartonFlavour[0])')
                    .Define('jet2_partonFlavour', 'abs(goodPartonFlavour[1])')
                    .Define('jetFar_ptCharm','(abs(goodPartonFlavour[index_CloseFar[1]])==4) ? Jet_cRegCorr[goodJets][index_CloseFar[1]] * goodJetPt[index_CloseFar[1]]:-1.')
                    .Define('jetFar_ptGluon','(abs(goodPartonFlavour[index_CloseFar[1]])==21) ? Jet_cRegCorr[goodJets][index_CloseFar[1]] * goodJetPt[index_CloseFar[1]]:-1.')
                    .Define('jetFar_CvLCharm','(abs(goodPartonFlavour[index_CloseFar[1]])==4) ? goodJetCvL[index_CloseFar[1]]:-1.')
                    .Define('jetFar_CvLGluon','(abs(goodPartonFlavour[index_CloseFar[1]])==21) ? goodJetCvL[index_CloseFar[1]]:-1.')
                    .Define('jetClose_partonFlavour','abs(goodPartonFlavour[index_CloseFar[0]])')
                    .Define('jetFar_partonFlavour','abs(goodPartonFlavour[index_CloseFar[1]])')
                    .Define('jetClose_Scale','goodJetPt[index_CloseFar[0]]/GenJet_pt[Jet_genJetIdx[goodJets][index_CloseFar[0]]]')
                    .Define('jetFar_Scale','goodJetPt[index_CloseFar[1]]/GenJet_pt[Jet_genJetIdx[goodJets][index_CloseFar[1]]]')
                    .Define('jetClose_cRegCorrScale','goodJetPt[index_CloseFar[0]]*Jet_cRegCorr[goodJets][index_CloseFar[0]]/GenJet_pt[Jet_genJetIdx[goodJets][index_CloseFar[0]]]')
                    .Define('jetFar_cRegCorrScale','goodJetPt[index_CloseFar[1]]*Jet_cRegCorr[goodJets][index_CloseFar[1]]/GenJet_pt[Jet_genJetIdx[goodJets][index_CloseFar[1]]]')     
        )
        branches += ['goodPartonFlavour']
        branches += get_rdf_branches('jet_mconly')
    return new_rdf, branches, cut_flow_dict

def rdf_def_higgs(rdf, branches=[], cut_flow_dict={}, filter=True):
    '''Higgs RDF definition.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        branches (list(str), optional): List of TBranches.
            Defaults to [].
        cut_flow_dict (dict(str: float), optional): The dictionary containing the cut flow.
            Defaults to {}.
        filter (bool, optional): Whether to filter.
            Defaults to True.

    Returns:
        new_rdf (ROOT.RDataFrame): Modified ROOT.RDataFrame.
        branches (list(str)): Updated list of TBranches.
        cut_flow_dict (dict(str: float)): Updated dictionary containing the cut flow.
    '''
    load_functions('reco')
    new_rdf = rdf.Define('higgs_mass_corr',
                        ('Minv3massiveCorr(goodJetPt, goodJetEta, goodJetPhi, goodJetMass,' +\
                        'Jet_cRegCorr[goodJets], Jet_muonIdx1[goodJets][index_CloseFar[0]],' +\
                        'Jet_muonIdx2[goodJets][index_CloseFar[0]],' +\
                        'Muon_pt, Muon_eta, Muon_phi,' +\
                        'Jpsi_muon1_pt, Jpsi_muon1_eta, Jpsi_muon1_phi,' +\
                        'Jpsi_muon2_pt, Jpsi_muon2_eta, Jpsi_muon2_phi,' +\
                        'Jpsi_kin_pt, Jpsi_kin_eta, Jpsi_kin_phi, Jpsi_kin_mass, index_CloseFar[0])'))
    branches += get_rdf_branches('higgs')
    return new_rdf, branches, cut_flow_dict

def rdf_def_genpart(rdf, branches=[]): # TODO: rename branches so that they start with 'gen'
    '''RDF define gen particles.

    Args:
        rdf (ROOT.RDataFrame): The ROOT.RDataFrame object.
        branches (list(str), optional): List of TBranches.
            Defaults to [].

    Returns:
        new_rdf (ROOT.RDataFrame): Modified RDataFrame.
        branches (list(str)): Updated list of TBranches.
    '''
    load_functions(mode='gen')

    # Find Higgs
    new_rdf = (rdf.Define('GenPart_Higgs_idx',
                        'HiggsIdx(GenPart_pdgId, GenPart_genPartIdxMother)')
                .Define('gen_Higgs_energy',
                        'GenPart_energy[GenPart_Higgs_idx]')
                .Define('gen_Higgs_eta',
                        'GenPart_eta[GenPart_Higgs_idx]')
                .Define('gen_Higgs_mass',
                        'GenPart_mass[GenPart_Higgs_idx]')
                .Define('gen_Higgs_phi',
                        'GenPart_phi[GenPart_Higgs_idx]')
                .Define('gen_Higgs_pt',
                        'GenPart_pt[GenPart_Higgs_idx]')
                .Define('gen_Higgs_px',
                        'GenPart_px[GenPart_Higgs_idx]')
                .Define('gen_Higgs_py',
                        'GenPart_py[GenPart_Higgs_idx]')
                .Define('gen_Higgs_pz',
                        'GenPart_pz[GenPart_Higgs_idx]')
                # Find Higgs Daughter
                .Define('GenPart_HiggsDaughters_pdgId',
                        'HiggsDaughtersPDG(GenPart_pdgId, GenPart_genPartIdxMother)')
                .Define('GenPart_HiggsDaughters_idx',
                        'HiggsDaughtersIdx(GenPart_pdgId, GenPart_genPartIdxMother)')
                .Define('GenPart_HiggsGrandDaughters_pdgId',
                        'GenericDaughtersPDG(GenPart_pdgId, GenPart_genPartIdxMother, GenPart_HiggsDaughters_idx)')
                .Define('GenPart_HiggsGrandDaughters_idx',
                        'GenericDaughtersIdx(GenPart_pdgId, GenPart_genPartIdxMother, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_energy',
                        'SelectByIdx(GenPart_energy, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_eta',
                        'SelectByIdx(GenPart_eta, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_mass',
                        'SelectByIdx(GenPart_mass, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_phi',
                        'SelectByIdx(GenPart_phi, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_pt',
                        'SelectByIdx(GenPart_pt, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_px',
                        'SelectByIdx(GenPart_px, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_py',
                        'SelectByIdx(GenPart_py, GenPart_HiggsDaughters_idx)')
                .Define('gen_HiggsDaughters_pz',
                        'SelectByIdx(GenPart_pz, GenPart_HiggsDaughters_idx)')   
    )

    # Get muons
    new_rdf = (new_rdf.Define('gen_muminus_index', 'IndexFindPDG(GenPart_HiggsDaughters_pdgId, 13)') # muon
                    .Define('gen_muplus_index', 'IndexFindPDG(GenPart_HiggsDaughters_pdgId, -13)') # anti-muon
                    .Define('gen_muminus_mass', 'gen_HiggsDaughters_mass[gen_muminus_index]')
                    .Define('gen_muminus_energy', 'gen_HiggsDaughters_energy[gen_muminus_index]')
                    .Define('gen_muminus_phi', 'gen_HiggsDaughters_phi[gen_muminus_index]')
                    .Define('gen_muminus_eta', 'gen_HiggsDaughters_eta[gen_muminus_index]')
                    .Define('gen_muminus_pt', 'gen_HiggsDaughters_pt[gen_muminus_index]')
                    .Define('gen_muminus_px', 'gen_HiggsDaughters_px[gen_muminus_index]')
                    .Define('gen_muminus_py', 'gen_HiggsDaughters_py[gen_muminus_index]')
                    .Define('gen_muminus_pz', 'gen_HiggsDaughters_pz[gen_muminus_index]')
                    .Define('gen_muplus_mass', 'gen_HiggsDaughters_mass[gen_muplus_index]')
                    .Define('gen_muplus_energy', 'gen_HiggsDaughters_energy[gen_muplus_index]')
                    .Define('gen_muplus_phi', 'gen_HiggsDaughters_phi[gen_muplus_index]')
                    .Define('gen_muplus_eta', 'gen_HiggsDaughters_eta[gen_muplus_index]')
                    .Define('gen_muplus_pt', 'gen_HiggsDaughters_pt[gen_muplus_index]')
                    .Define('gen_muplus_px', 'gen_HiggsDaughters_px[gen_muplus_index]')
                    .Define('gen_muplus_py', 'gen_HiggsDaughters_py[gen_muplus_index]')
                    .Define('gen_muplus_pz', 'gen_HiggsDaughters_pz[gen_muplus_index]')
    )

    # Get muon-muon separation
    new_rdf = (new_rdf.Define('gen_dR_muminus_muplus', 'DeltaR(gen_muminus_eta, gen_muminus_phi, gen_muplus_eta, gen_muplus_phi)')
                    .Define('gen_deta_muminus_muplus', 'gen_muminus_eta - gen_muplus_eta')
                    .Define('gen_dphi_muminus_muplus', 'gen_muminus_phi - gen_muplus_phi')
                    .Define('gen_dpt_muminus_muplus', 'gen_muminus_pt - gen_muplus_pt')
                    .Define('gen_dE_muminus_muplus', 'gen_muminus_energy - gen_muplus_energy')
    )

    # Get J/Psi
    new_rdf = (new_rdf.Define('gen_JPsi_cand',
                            'SumPxPyPzE(gen_muminus_px, gen_muminus_py, gen_muminus_pz, gen_muminus_energy,\
                            gen_muplus_px, gen_muplus_py, gen_muplus_pz, gen_muplus_energy)')
                    .Define('gen_JPsi_cand_mass', 'gen_JPsi_cand.M()')
                    .Define('gen_JPsi_cand_eta', 'gen_JPsi_cand.Eta()')
                    .Define('gen_JPsi_cand_phi', 'gen_JPsi_cand.Phi()')
                    .Define('gen_JPsi_cand_p', 'gen_JPsi_cand.P()')
                    .Define('gen_JPsi_cand_pt', 'gen_JPsi_cand.Pt()')
                    .Define('gen_JPsi_cand_mt', 'gen_JPsi_cand.Mt()')
                    .Define('gen_JPsi_cand_energy', 'gen_JPsi_cand.E()')
    )

    # Get charms
    new_rdf = (new_rdf.Define('gen_charm_index', 'IndexFindPDG(GenPart_HiggsDaughters_pdgId, 4)')  # charm
                    .Define('gen_anticharm_index', 'IndexFindPDG(GenPart_HiggsDaughters_pdgId, -4)') # anti-charm
                    .Define('gen_charm_mass', 'gen_HiggsDaughters_mass[gen_charm_index]')
                    .Define('gen_charm_energy', 'gen_HiggsDaughters_energy[gen_charm_index]')
                    .Define('gen_charm_phi', 'gen_HiggsDaughters_phi[gen_charm_index]')
                    .Define('gen_charm_eta', 'gen_HiggsDaughters_eta[gen_charm_index]')
                    .Define('gen_charm_pt', 'gen_HiggsDaughters_pt[gen_charm_index]')
                    .Define('gen_charm_px', 'gen_HiggsDaughters_px[gen_charm_index]')
                    .Define('gen_charm_py', 'gen_HiggsDaughters_py[gen_charm_index]')
                    .Define('gen_charm_pz', 'gen_HiggsDaughters_pz[gen_charm_index]')
                    .Define('gen_anticharm_mass', 'gen_HiggsDaughters_mass[gen_anticharm_index]')
                    .Define('gen_anticharm_energy', 'gen_HiggsDaughters_energy[gen_anticharm_index]')
                    .Define('gen_anticharm_phi', 'gen_HiggsDaughters_phi[gen_anticharm_index]')
                    .Define('gen_anticharm_eta', 'gen_HiggsDaughters_eta[gen_anticharm_index]')
                    .Define('gen_anticharm_pt', 'gen_HiggsDaughters_pt[gen_anticharm_index]')
                    .Define('gen_anticharm_px', 'gen_HiggsDaughters_px[gen_anticharm_index]')
                    .Define('gen_anticharm_py', 'gen_HiggsDaughters_py[gen_anticharm_index]')
                    .Define('gen_anticharm_pz', 'gen_HiggsDaughters_pz[gen_anticharm_index]')
                    .Define('sorted_charm_indices', 'SortByPt(gen_charm_index, gen_anticharm_index, gen_HiggsDaughters_pt)')
                    .Define('gen_leadcharm_index', 'sorted_charm_indices[0]') # leading charm
                    .Define('gen_subcharm_index', 'sorted_charm_indices[1]')  # sub-leading charm
                    .Define('gen_leadcharm_pdgId', 'GenPart_HiggsDaughters_pdgId[gen_leadcharm_index]')
                    .Define('gen_leadcharm_mass', 'gen_HiggsDaughters_mass[gen_leadcharm_index]')
                    .Define('gen_leadcharm_energy', 'gen_HiggsDaughters_energy[gen_leadcharm_index]')
                    .Define('gen_leadcharm_phi', 'gen_HiggsDaughters_phi[gen_leadcharm_index]')
                    .Define('gen_leadcharm_eta', 'gen_HiggsDaughters_eta[gen_leadcharm_index]')
                    .Define('gen_leadcharm_pt', 'gen_HiggsDaughters_pt[gen_leadcharm_index]')
                    .Define('gen_leadcharm_px', 'gen_HiggsDaughters_px[gen_leadcharm_index]')
                    .Define('gen_leadcharm_py', 'gen_HiggsDaughters_py[gen_leadcharm_index]')
                    .Define('gen_leadcharm_pz', 'gen_HiggsDaughters_pz[gen_leadcharm_index]')
                    .Define('gen_subcharm_pdgId', 'GenPart_HiggsDaughters_pdgId[gen_subcharm_index]')
                    .Define('gen_subcharm_mass', 'gen_HiggsDaughters_mass[gen_subcharm_index]')
                    .Define('gen_subcharm_energy', 'gen_HiggsDaughters_energy[gen_subcharm_index]')
                    .Define('gen_subcharm_phi', 'gen_HiggsDaughters_phi[gen_subcharm_index]')
                    .Define('gen_subcharm_eta', 'gen_HiggsDaughters_eta[gen_subcharm_index]')
                    .Define('gen_subcharm_pt', 'gen_HiggsDaughters_pt[gen_subcharm_index]')
                    .Define('gen_subcharm_px', 'gen_HiggsDaughters_px[gen_subcharm_index]')
                    .Define('gen_subcharm_py', 'gen_HiggsDaughters_py[gen_subcharm_index]')
                    .Define('gen_subcharm_pz', 'gen_HiggsDaughters_pz[gen_subcharm_index]')
    )

    # Get charm-charm separation
    new_rdf = (new_rdf.Define('gen_dR_charm_anticharm', 'DeltaR(gen_charm_eta, gen_charm_phi, gen_anticharm_eta, gen_anticharm_phi)')
                    .Define('gen_deta_charm_anticharm', 'gen_charm_eta - gen_anticharm_eta')
                    .Define('gen_dphi_charm_anticharm', 'gen_charm_phi - gen_anticharm_phi')
                    .Define('gen_dpt_charm_anticharm', 'gen_charm_pt - gen_anticharm_pt')
                    .Define('gen_dpt_leadcharm_subcharm', 'gen_leadcharm_pt - gen_subcharm_pt')
    )

    # Get di-charm
    new_rdf = (new_rdf.Define('gen_dicharm_cand',
                            'SumPxPyPzE(gen_charm_px, gen_charm_py, gen_charm_pz, gen_charm_energy,\
                            gen_anticharm_px, gen_anticharm_py, gen_anticharm_pz, gen_anticharm_energy)')
                    .Define('gen_dicharm_cand_mass', 'gen_dicharm_cand.M()')
                    .Define('gen_dicharm_cand_eta', 'gen_dicharm_cand.Eta()')
                    .Define('gen_dicharm_cand_phi', 'gen_dicharm_cand.Phi()')
                    .Define('gen_dicharm_cand_p', 'gen_dicharm_cand.P()')
                    .Define('gen_dicharm_cand_pt', 'gen_dicharm_cand.Pt()')
                    .Define('gen_dicharm_cand_mt', 'gen_dicharm_cand.Mt()')
                    .Define('gen_dicharm_cand_energy', 'gen_dicharm_cand.E()')
    )

    # Get charm-JPsi separation
    new_rdf = (new_rdf.Define('gen_dR_charm_JPsi', 'DeltaR(gen_charm_eta, gen_charm_phi, gen_JPsi_cand_eta, gen_JPsi_cand_phi)')
                    .Define('gen_deta_charm_JPsi', 'gen_charm_eta - gen_JPsi_cand_eta')
                    .Define('gen_dphi_charm_JPsi', 'gen_charm_phi - gen_JPsi_cand_phi')
                    .Define('gen_dpt_charm_JPsi', 'gen_charm_pt - gen_JPsi_cand_pt')
                    .Define('gen_dR_anticharm_JPsi', 'DeltaR(gen_anticharm_eta, gen_anticharm_phi, gen_JPsi_cand_eta, gen_JPsi_cand_phi)')
                    .Define('gen_deta_anticharm_JPsi', 'gen_anticharm_eta - gen_JPsi_cand_eta')
                    .Define('gen_dphi_anticharm_JPsi', 'gen_anticharm_phi - gen_JPsi_cand_phi')
                    .Define('gen_dpt_anticharm_JPsi', 'gen_anticharm_pt - gen_JPsi_cand_pt')
                    .Define('gen_dR_leadcharm_JPsi', 'DeltaR(gen_leadcharm_eta, gen_leadcharm_phi, gen_JPsi_cand_eta, gen_JPsi_cand_phi)')
                    .Define('gen_deta_leadcharm_JPsi', 'gen_leadcharm_eta - gen_JPsi_cand_eta')
                    .Define('gen_dphi_leadcharm_JPsi', 'gen_leadcharm_phi - gen_JPsi_cand_phi')
                    .Define('gen_dpt_leadcharm_JPsi', 'gen_leadcharm_pt - gen_JPsi_cand_pt')
                    .Define('gen_dR_subcharm_JPsi', 'DeltaR(gen_subcharm_eta, gen_subcharm_phi, gen_JPsi_cand_eta, gen_JPsi_cand_phi)')
                    .Define('gen_deta_subcharm_JPsi', 'gen_subcharm_eta - gen_JPsi_cand_eta')
                    .Define('gen_dphi_subcharm_JPsi', 'gen_subcharm_phi - gen_JPsi_cand_phi')
                    .Define('gen_dpt_subcharm_JPsi', 'gen_subcharm_pt - gen_JPsi_cand_pt')
    )

    # Get dicharm-JPsi separation
    new_rdf = (new_rdf.Define('gen_dR_dicharm_JPsi', 'DeltaR(gen_dicharm_cand_eta, gen_dicharm_cand_phi, gen_JPsi_cand_eta, gen_JPsi_cand_phi)')
                    .Define('gen_deta_dicharm_JPsi', 'gen_dicharm_cand_eta - gen_JPsi_cand_eta')
                    .Define('gen_dphi_dicharm_JPsi', 'gen_dicharm_cand_phi - gen_JPsi_cand_phi')
                    .Define('gen_dpt_dicharm_JPsi', 'gen_dicharm_cand_pt - gen_JPsi_cand_pt')
    )

    # Get Higgs
    new_rdf = (new_rdf.Define('Higgs_cand',
                            'SumPtEtaPhiE(gen_dicharm_cand_pt, gen_dicharm_cand_eta, gen_dicharm_cand_phi, gen_dicharm_cand_energy,\
                            gen_JPsi_cand_pt, gen_JPsi_cand_eta, gen_JPsi_cand_phi, gen_JPsi_cand_energy)')
                    .Define('gen_Higgs_cand_mass', 'Higgs_cand.M()')
                    .Define('gen_Higgs_cand_eta', 'Higgs_cand.Eta()')
                    .Define('gen_Higgs_cand_phi', 'Higgs_cand.Phi()')
                    .Define('gen_Higgs_cand_p', 'Higgs_cand.P()')
                    .Define('gen_Higgs_cand_pt', 'Higgs_cand.Pt()')
                    .Define('gen_Higgs_cand_mt', 'Higgs_cand.Mt()')
                    .Define('gen_Higgs_cand_energy', 'Higgs_cand.E()')
    )

    # Branches
    branches += ['GenPart_Higgs_idx',
                'gen_Higgs_energy',
                'gen_Higgs_eta',
                'gen_Higgs_mass',
                'gen_Higgs_phi',
                'gen_Higgs_pt',
                'gen_Higgs_px',
                'gen_Higgs_py',
                'gen_Higgs_pz']
    
    branches += ['GenPart_HiggsDaughters_pdgId',
                'GenPart_HiggsDaughters_idx',
                'GenPart_HiggsGrandDaughters_pdgId',
                'GenPart_HiggsGrandDaughters_idx',
                'gen_HiggsDaughters_energy',
                'gen_HiggsDaughters_eta',
                'gen_HiggsDaughters_mass',
                'gen_HiggsDaughters_phi',
                'gen_HiggsDaughters_pt',
                'gen_HiggsDaughters_px',
                'gen_HiggsDaughters_py',
                'gen_HiggsDaughters_pz']
    
    branches += ['gen_JPsi_cand_mass',
                'gen_JPsi_cand_eta',
                'gen_JPsi_cand_phi',
                'gen_JPsi_cand_p',
                'gen_JPsi_cand_pt',
                'gen_JPsi_cand_mt',
                'gen_JPsi_cand_energy',
                'gen_dicharm_cand_mass',
                'gen_dicharm_cand_eta',
                'gen_dicharm_cand_phi',
                'gen_dicharm_cand_p',
                'gen_dicharm_cand_pt',
                'gen_dicharm_cand_mt',
                'gen_dicharm_cand_energy',
                'gen_Higgs_cand_mass',
                'gen_Higgs_cand_eta',
                'gen_Higgs_cand_phi',
                'gen_Higgs_cand_p',
                'gen_Higgs_cand_pt',
                'gen_Higgs_cand_mt',
                'gen_Higgs_cand_energy']
    
    branches += ['gen_dR_muminus_muplus',
                'gen_deta_muminus_muplus',
                'gen_dphi_muminus_muplus',
                'gen_dpt_muminus_muplus',
                'gen_dE_muminus_muplus',
                'gen_dR_charm_anticharm',
                'gen_deta_charm_anticharm',
                'gen_dphi_charm_anticharm',
                'gen_dpt_charm_anticharm',
                'gen_dpt_leadcharm_subcharm',
                'gen_dR_charm_JPsi',
                'gen_deta_charm_JPsi',
                'gen_dphi_charm_JPsi',
                'gen_dpt_charm_JPsi',
                'gen_dR_anticharm_JPsi',
                'gen_deta_anticharm_JPsi',
                'gen_dphi_anticharm_JPsi',
                'gen_dpt_anticharm_JPsi',
                'gen_dR_leadcharm_JPsi',
                'gen_deta_leadcharm_JPsi',
                'gen_dphi_leadcharm_JPsi',
                'gen_dpt_leadcharm_JPsi',
                'gen_dR_subcharm_JPsi',
                'gen_deta_subcharm_JPsi',
                'gen_dphi_subcharm_JPsi',
                'gen_dpt_subcharm_JPsi',
                'gen_dR_dicharm_JPsi',
                'gen_deta_dicharm_JPsi',
                'gen_dphi_dicharm_JPsi',
                'gen_dpt_dicharm_JPsi']
    
    branches += ['gen_muminus_mass',
                'gen_muminus_energy',
                'gen_muminus_eta',
                'gen_muminus_phi',
                'gen_muminus_pt',
                'gen_muminus_px',
                'gen_muminus_py',
                'gen_muminus_pz',
                'gen_muplus_mass',
                'gen_muplus_energy',
                'gen_muplus_eta',
                'gen_muplus_phi',
                'gen_muplus_pt',
                'gen_muplus_px',
                'gen_muplus_py',
                'gen_muplus_pz',
                'gen_charm_mass',
                'gen_charm_energy',
                'gen_charm_eta',
                'gen_charm_phi',
                'gen_charm_pt',
                'gen_charm_px',
                'gen_charm_py',
                'gen_charm_pz',
                'gen_anticharm_mass',
                'gen_anticharm_energy',
                'gen_anticharm_eta',
                'gen_anticharm_phi',
                'gen_anticharm_pt',
                'gen_anticharm_px',
                'gen_anticharm_py',
                'gen_anticharm_pz',
                'gen_leadcharm_pdgId',
                'gen_leadcharm_mass',
                'gen_leadcharm_energy',
                'gen_leadcharm_phi',
                'gen_leadcharm_eta',
                'gen_leadcharm_pt',
                'gen_leadcharm_px',
                'gen_leadcharm_py',
                'gen_leadcharm_pz',
                'gen_subcharm_pdgId',
                'gen_subcharm_mass',
                'gen_subcharm_energy',
                'gen_subcharm_phi',
                'gen_subcharm_eta',
                'gen_subcharm_pt',
                'gen_subcharm_px',
                'gen_subcharm_py',
                'gen_subcharm_pz']
    
    return new_rdf, branches