'''

Common definition of Zee selection used in ZH analysis

'''

from FinalStateAnalysis.TMegaSelector.megautil import And

def build_zee_selection(meta_tree):
    ''' Build the Zee selection '''
    meta = meta_tree
    selection = And(
        # Trigger selection
        # FIXME!!
        #meta.doubleMuPass > 0.5,

        # Leading muon selection
        meta.e1_e2_SS < 0.5,
        meta.e1_e2_Mass < 120,
        meta.e1_e2_Mass > 60,

        # Order the leading Z muons by PT so we only have one candidate per event
        meta.e1Pt > meta.e2Pt,

        meta.e1Pt > 20,
        meta.e2Pt > 10,

        # Apply Iso
        meta.e1RelPFIsoDB < 0.25,
        meta.e2RelPFIsoDB < 0.25,

        # Apply ID
        meta.e1CiCTight.bit(1),
        meta.e2CiCTight.bit(1),

        # Missing hits
        meta.e1MissingHits < 0.5,
        meta.e2MissingHits < 0.5,

        meta.e1AbsEta < 2.5,
        meta.e2AbsEta < 2.5,
    )
    return selection
