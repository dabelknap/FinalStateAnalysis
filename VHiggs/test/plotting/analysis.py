'''

Analyze trilepton WH(tautau) events.

Author: Evan K. Friis, UW Madison

Analysis is configured by analysis_cfg.py

'''

import ROOT
import os
import json
import sys
import logging
import uncertainties
import math
import FinalStateAnalysis.PatTools.data as data_tool
from FinalStateAnalysis.Utilities.AnalysisPlotter import styling,samplestyles
from FinalStateAnalysis.Utilities.Histo import Histo
from analysis_cfg import cfg

# Setup logging
logging.basicConfig(
    filename='analysis.log',level=logging.DEBUG, filemode='w')
log = logging.getLogger("analysis")
stderr_log = logging.StreamHandler()
log.addHandler(stderr_log)

def estimate_fake_sum(fr1, fr2, fr12s, fr12en):
    '''
    Estimate the total fake rate sum, with proper errors.

    Arguments
    ---------

    * fr1 and fr2 should be dictionaries with information about the two
      fake object types. They should have the following entries
      - en : yield in enriched region
      - ewk_s : estimated signal yield using EWK fake rate
      - qcd_s : estimated signal yield using QCD fake rate
      - 123 : estimated QCD fraction in enriched region
      - 123en : enriched QCD yield
    * fr12s and fr12en should give signal yield and enriched count for the
      double object fake rate

    '''
    ufloat = uncertainties.ufloat
    def get_rel_counting_err(number):
        ''' Get the relative counting error of a number '''
        return ufloat((1.0, math.sqrt(number)/number))

    # Error on fr1 signal estimate due to counting in enriched region
    def compute_errors(fakerate):
        ''' Get the val and error from fr1 dictionary. '''
        # Counting error due to count in enriched region
        if not fakerate['en']:
            return ufloat((0, 0))
        enriched_region_error = get_rel_counting_err(fakerate['en'])
        qcd_in_enriched_region_error = get_rel_counting_err(fakerate['123en'])

        qcd_fraction = (fakerate['123']*qcd_in_enriched_region_error/
                        (fakerate['en']*enriched_region_error))

        est_yield = enriched_region_error*(
            (1 - qcd_fraction)*fakerate['ewk_s'] +
            qcd_fraction*fakerate['qcd_s'])
        return est_yield

    fake1est = compute_errors(fr1)
    fake2est = compute_errors(fr2)
    double_est = 0
    if fr12en:
        double_est = fr12s*get_rel_counting_err(fr12en)

    total_yield = fake1est + fake2est - double_est
    return total_yield

if __name__ == "__main__":
    ############################################################################
    ### Load the data ##########################################################
    ############################################################################
    int_lumi = 4600
    skips = ['DoubleEl', 'EM']
    samples, plotter = data_tool.build_data(
        'VH', '2011-12-10-v1-WHAnalyze', 'scratch_results',
        int_lumi, skips, count='emt/skimCounter')

    canvas = ROOT.TCanvas("basdf", "aasdf", 800, 600)

    shape_file = ROOT.TFile("wh_shapes.root", 'RECREATE')

    mc_legend = plotter.build_legend(
        '/mmt/skimCounter', exclude = ['data*', '*VH*'], drawopt='lf',
        xlow = 0.6, ylow=0.5,)

    ############################################################################
    ### Loop over all channels to analyze  #####################################
    ############################################################################
    for channel, channel_cfg in cfg.iteritems():
        log.info("Analyzing channel: %s", channel)
        # Unpack the configuration
        ntuple = channel_cfg['ntuple']
        # A dictionary describing how to plot variables
        variables = channel_cfg['variables']
        # The baseline selection
        baseline = channel_cfg['baseline']
        # Get samples to exclude
        exclude = channel_cfg['exclude']
        # Get primary dataset
        primds = channel_cfg['primds']

        ########################################################################
        ### Loop over all charge configurations ################################
        ########################################################################
        for charge_cat, charge_cat_cfg in channel_cfg['charge_categories'].iteritems():
            log.info("-- charge category: %s", charge_cat)
            # Any extra selections specific to this charge_cat.  The charge
            # selection should be included in this.  This is an extension of the
            # "baseline"
            extra_selections = charge_cat_cfg['cat_baseline']
            # The final analysis cuts
            final_selections = charge_cat_cfg['selections']['final']['cuts']

            # Get the configuration for the fake objects
            object1_cfg = charge_cat_cfg['object1']
            object2_cfg = charge_cat_cfg['object2']
            object3_cfg = charge_cat_cfg['object3']

            ####################################################################
            ### First, select the final events #################################
            ####################################################################
            log.info("---- selecting final events in data...")
            ultimate_selection = baseline + extra_selections + final_selections\
                    + object1_cfg['pass'] + object2_cfg['pass'] + \
                    object3_cfg['pass']

            run_evts = plotter.get_run_lumi_evt(
                ntuple, ' && '.join(ultimate_selection),
                include='*data*', exclude=exclude
            )
            run_event_filename = '%s_%s_events.json' % (channel, charge_cat)
            with open(run_event_filename, 'w') as run_evt_file:
                run_evt_file.write(json.dumps(run_evts, indent=4))

            ####################################################################
            ### Now, loop over each selection type  ############################
            ####################################################################
            selection_cfgs = charge_cat_cfg['selections']
            for selection_name, selection_cfg in selection_cfgs.iteritems():
                log.info("---- now running selection %s", selection_name)

                def saveplot(filename):
                    # Save the current canvas
                    filetype = '.pdf'
                    canvas.SetLogy(False)
                    canvas.Update()
                    filename = os.path.join("plots", channel, charge_cat,
                                            filename + filetype)
                    log.info('saving %s', filename)
                    canvas.Print(filename)
                    canvas.SetLogy(True)
                    canvas.Update()
                    canvas.Print(filename.replace(filetype, '_log' + filetype))

                # Cuts in this selection
                extra_cuts = selection_cfg['cuts']
                vars_to_draw = selection_cfg['vars']

                for var in vars_to_draw:
                    log.info("------ doing variable %s", var)
                    plot_base_name = '_'.join(
                        [channel, charge_cat, selection_name, var])
                    if var not in variables:
                        log.info("------- skipping variable %s!", var)
                        continue

                    # Unpack variable info
                    to_plot, xaxis_title, binning, rebin = variables[var]

                    def register_tree(label, the_selections, weight):
                        plotter.register_tree(
                            plot_base_name + '_' + label,
                            ntuple,
                            to_plot,
                            ' && '.join(the_selections),
                            w = weight,
                            binning = binning,
                            include = ['*'],
                            exclude = exclude,
                        )

                    ############################################################
                    ### Loose and ultimate selections ##########################
                    ############################################################
                    # Make the loose selection
                    log.info("------ running loose selection...")
                    loose_selection = baseline + extra_selections + extra_cuts
                    register_tree('loose', loose_selection, '(pu2011AB)')

                    log.info("------ running ultimate selection...")
                    # Make the ultimate selection
                    ult_selection = baseline + extra_selections + extra_cuts \
                            + object1_cfg['pass'] \
                            + object2_cfg['pass'] \
                            + object3_cfg['pass']
                    register_tree('ult', ult_selection, '(pu2011AB)')

                    ############################################################
                    ### Compute fake rate estimates ############################
                    ############################################################

                    log.info("------ running fake object #1 enriched selection...")
                    # Make the fake1 enriched
                    fr1en_selection = baseline + extra_selections + extra_cuts \
                            + object1_cfg['fail'] \
                            + object2_cfg['pass'] \
                            + object3_cfg['pass']
                    register_tree('fr1en', fr1en_selection, '(pu2011AB)')

                    log.info("------ apply fake object #1 EWK weights...")
                    # Extrapolate the fake1 enriched into the signal using ewk
                    # and qcd fake rates
                    register_tree('fr1s_ewk', fr1en_selection,
                                  '(pu2011AB)*(%s)' % object1_cfg['ewk_fr'])
                    log.info("------ apply fake object #1 QCD weights...")
                    register_tree('fr1s_qcd', fr1en_selection,
                                  '(pu2011AB)*(%s)' % object1_cfg['qcd_fr'])

                    # Make the fake2 enriched
                    log.info("------ running fake object #2 enriched selection...")
                    fr2en_selection = baseline + extra_selections + extra_cuts \
                            + object1_cfg['pass'] \
                            + object2_cfg['fail'] \
                            + object3_cfg['pass']
                    register_tree('fr2en', fr2en_selection, '(pu2011AB)')
                    # Extrapolate the fake2 enriched into the signal using ewk
                    # and qcd fake rates
                    log.info("------ apply fake object #2 EWK weights...")
                    register_tree('fr2s_ewk', fr2en_selection,
                                  '(pu2011AB)*(%s)' % object2_cfg['ewk_fr'])
                    log.info("------ apply fake object #2 QCD weights...")
                    register_tree('fr2s_qcd', fr2en_selection,
                                  '(pu2011AB)*(%s)' % object2_cfg['qcd_fr'])

                    # Make the double fake rate estimate
                    # Make the fake2 enriched
                    log.info("------ doing double fake object enriched selection...")
                    fr12en_selection = baseline + extra_selections + extra_cuts \
                            + object1_cfg['fail'] \
                            + object2_cfg['fail'] \
                            + object3_cfg['pass']
                    register_tree('fr12en', fr12en_selection, '(pu2011AB)')
                    # Extrapolate the fake2 enriched into the signal using ewk
                    # and qcd fake rates
                    log.info("------ applying double EWK weights...")
                    register_tree('fr12s_ewk', fr12en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object1_cfg['ewk_fr'],
                                      object2_cfg['ewk_fr']
                                  ))
                    log.info("------ applying double QCD weights...")
                    register_tree('fr12s_qcd', fr12en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object1_cfg['qcd_fr'],
                                      object2_cfg['qcd_fr']
                                  ))

                    # Make the triple fake rate estimate
                    # Make the fake2 enriched
                    log.info("------ selecting triple fakes...")
                    fr123en_selection = baseline + extra_selections + extra_cuts \
                            + object1_cfg['fail'] \
                            + object2_cfg['fail'] \
                            + object3_cfg['fail']
                    # Extrapolate the fake2 enriched into the signal using ewk
                    # and qcd fake rates
                    register_tree('fr123en', fr123en_selection, '(pu2011AB)')

                    # Extrapolate from triple fakes into fake1 enriched region
                    log.info("------ extrapolating (EWK) triple fakes into fake #1 region")
                    register_tree('fr123en1_ewk', fr123en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object2_cfg['ewk_fr'],
                                      object3_cfg['ewk_fr']
                                  ))
                    log.info("------ extrapolating (QCD) triple fakes into fake #1 region")
                    register_tree('fr123en1_qcd', fr123en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object2_cfg['qcd_fr'],
                                      object3_cfg['qcd_fr']
                                  ))
                    log.info("------ extrapolating (EWK) triple fakes into fake #2 region")
                    # Extrapolate from triple fakes into fake2 enriched region
                    register_tree('fr123en2_ewk', fr123en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object1_cfg['ewk_fr'],
                                      object3_cfg['ewk_fr']
                                  ))
                    log.info("------ extrapolating (QCD) triple fakes into fake #2 region")
                    register_tree('fr123en2_qcd', fr123en_selection,
                                  '(pu2011AB)*(%s)*(%s)' % (
                                      object1_cfg['qcd_fr'],
                                      object3_cfg['qcd_fr']
                                  ))

                    log.info("------ extrapolating (EWK) triple fakes into double fake 2 region")
                    register_tree('fr123en12_ewk', fr123en_selection,
                                  '(pu2011AB)*(%s)' % (
                                      object3_cfg['ewk_fr']
                                  ))
                    log.info("------ extrapolating (QCD) triple fakes into double fake 2 region")
                    register_tree('fr123en12_qcd', fr123en_selection,
                                  '(pu2011AB)*(%s)' % (
                                      object3_cfg['qcd_fr']
                                  ))

                    ############################################################
                    ### Make some motherfucking plots ##########################
                    ############################################################

                    # First, just do all the plots where we only use MC
                    mc_plots = [
                        'loose', 'ult',
                        'fr1en', 'fr2en', 'fr12en',
                        'fr1s_ewk', 'fr2s_ewk', 'fr12s_ewk',
                        'fr1s_qcd', 'fr2s_qcd', 'fr12s_qcd',
                        'fr123en'
                    ]
                    for plot in mc_plots:
                        plot_name = plot_base_name + '_' + plot
                        stack = plotter.build_stack(
                            ntuple + ':' + plot_name,
                            include = ['*'],
                            exclude = ['data*', '*VH*'],
                            rebin = rebin, show_overflows=True,
                        )
                        data = plotter.get_histogram(
                            primds, ntuple + ':' + plot_name,
                            rebin = rebin, show_overflows=True,
                        )
                        stack.Draw()
                        data.Draw('same,pe,x0')
                        stack.SetMaximum(max(
                            stack.GetHistogram().GetMaximum(),
                            data.GetMaximum()))
                        stack.GetXaxis().SetTitle(xaxis_title)
                        mc_legend.Draw()
                        canvas.Update()
                        saveplot(plot_name + '_mc')

                    ############################################################
                    ### Now make control plots of the background regions #######
                    ############################################################

                    # We need to plot
                    # Each of the single fake rate CRs w/ QCD
                    # The total final prediction, with double fake correction
                    # overlayed.
                    # The total final prediction with stack FRs with double fake
                    # correction overlayed.
                    # Final prediction with combined fake rate

                    # So we we want fr1en (data), with fr123en1_qcd
                    for region in ['1', '2', '12']:
                        data_plot_name = 'fr%sen' % region
                        triple_fakes = 'fr123en%s_qcd' % region
                        data_plot = plotter.get_histogram(
                            primds,
                            ntuple + ':' + plot_base_name + '_' + data_plot_name,
                            rebin = rebin, show_overflows=True,
                        )
                        fake_plot = plotter.get_histogram(
                            primds,
                            ntuple + ':' + plot_base_name + '_' + triple_fakes,
                            rebin = rebin, show_overflows=True,
                        )
                        fake_plot.SetLineWidth(2)
                        fake_plot.SetLineColor(ROOT.EColor.kRed)
                        legend = ROOT.TLegend(0.6, 0.6, 0.9, 0.90, "", "brNDC")
                        legend.SetFillStyle(0)
                        legend.AddEntry(data_plot.th1, "data", "lpe,x0")
                        legend.AddEntry(fake_plot.th1, "QCD est.", "l")
                        data_plot.Draw('pe,x0')
                        fake_plot.Draw('same')
                        legend.Draw()
                        saveplot(plot_name + data_plot_name + '_wqcd')

                    ############################################################
                    ### Get the signal yields for all fake rate types    #######
                    ############################################################

                    data_fr1s_ewk = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr1s_ewk',
                        rebin = rebin, show_overflows=True,
                    )
                    data_fr2s_ewk = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr2s_ewk',
                        rebin = rebin, show_overflows=True,
                    )
                    data_fr1s_qcd = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr1s_qcd',
                        rebin = rebin, show_overflows=True,
                    )
                    data_fr2s_qcd = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr2s_qcd',
                        rebin = rebin, show_overflows=True,
                    )
                    data_fr12s_ewk = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr12s_ewk',
                        rebin = rebin, show_overflows=True,
                    )
                    data_fr12s_qcd = plotter.get_histogram(
                        primds,
                        ntuple + ':' + plot_base_name + '_fr12s_qcd',
                        rebin = rebin, show_overflows=True,
                    )

                    ############################################################
                    ### The final selected data events #########################
                    ############################################################

                    ult_data = plotter.get_histogram(
                        primds, ntuple + ':' + plot_base_name + '_ult',
                        rebin = rebin, show_overflows=True,
                    )

                    ############################################################
                    ### Corrected WZ and ZZ for fake rate contamination  #######
                    ############################################################
                    # (these only use EWK FR)
                    corrected_mc = ['ZZ', 'WZ']
                    corrected_mc_histos = []
                    for to_correct in corrected_mc:
                        log.info("------- correcting final %s MC", to_correct)
                        mc_final = plotter.get_histogram(
                            to_correct,
                            ntuple + ':' + plot_base_name + '_ult',
                            rebin = rebin, show_overflows = True
                        )
                        log.info("-------- initial yield %0.2f",
                                 mc_final.Integral())
                        # Get the contribution from the FR method
                        mc_fake1_bkg_fr = plotter.get_histogram(
                            to_correct,
                            ntuple + ':' + plot_base_name + '_fr1s_ewk',
                            rebin = rebin, show_overflows = True
                        )
                        log.info("-------- fake1 yield %0.2f",
                                 mc_fake1_bkg_fr.Integral())
                        mc_fake2_bkg_fr = plotter.get_histogram(
                            to_correct,
                            ntuple + ':' + plot_base_name + '_fr1s_ewk',
                            rebin = rebin, show_overflows = True
                        )
                        log.info("-------- fake2 yield %0.2f",
                                 mc_fake2_bkg_fr.Integral())
                        mc_correct = mc_final - mc_fake2_bkg_fr
                        mc_correct = mc_correct - mc_fake1_bkg_fr
                        corrected_mc_histos.append(mc_correct)

                    ############################################################
                    ### Make the stacked plot showing both fake sources  #######
                    ############################################################

                    signal = plotter.get_histogram(
                        'VH125',
                        ntuple + ':' + plot_base_name + '_ult',
                        rebin = rebin, show_overflows = True
                    )
                    stack = ROOT.THStack("FR_FINAL",
                                         "Final #mu#mu#tau selection")
                    legend = ROOT.TLegend(0.6, 0.6, 0.9, 0.90, "", "brNDC")
                    legend.SetFillStyle(0)
                    for histo_name, histo in zip(corrected_mc,
                                                 corrected_mc_histos):
                        stack.Add(histo.th1, 'hist')
                        legend.AddEntry(histo.th1, histo_name, 'lf')

                    styling.apply_style(data_fr1s_ewk,
                                        **samplestyles.SAMPLE_STYLES['ztt'])
                    stack.Add(data_fr1s_ewk.th1, 'hist')
                    legend.AddEntry(data_fr1s_ewk.th1,
                                    "%s fakes" % object1_cfg['name'], "lf")
                    styling.apply_style(data_fr2s_ewk,
                                        **samplestyles.SAMPLE_STYLES['QCD*'])
                    stack.Add(data_fr2s_ewk.th1, 'hist')
                    legend.AddEntry(data_fr2s_ewk.th1,
                                    "%s fakes" % object2_cfg['name'], "lf")
                    stack.Draw()
                    ult_data.Draw('same, pe,x0')
                    legend.Draw()
                    stack.SetMaximum(2.*max(
                        stack.GetHistogram().GetMaximum(),
                        ult_data.GetMaximum()))

                    saveplot(plot_base_name + '_ult_wfrs')

                    ############################################################
                    ### Now do the full error estimation of the fake bkgs ######
                    ############################################################

                    # Uncertainty prescription
                    # For each bin
                    # For a single fake rates
                    # Have an EWK and QCD signal region estimate
                    # Get the fraction F of QCD in the enriched region
                    # total yield = (1 - F)*EWK_s + F*QCD_s
                    # Assume double fakes are dominated by QCD FIXME?

                    def get_data_fr_yield(region, bin):
                        histo = plotter.get_histogram(
                            primds,
                            ntuple + ':' + plot_base_name + '_' + region,
                            rebin = rebin, show_overflows=True,
                        )
                        return histo.GetBinContent(bin)

                    # Loop over the bins
                    all_fakes = Histo(data_fr2s_ewk)
                    all_fakes.SetName(plot_base_name + "_all_fakes")
                    all_fakes.Reset()
                    styling.apply_style(all_fakes,
                                        **samplestyles.SAMPLE_STYLES['ztt'])

                    for i in range(0, data_fr2s_ewk.GetNbinsX()+2):
                        fake1 = {
                            'en' : get_data_fr_yield('fr1en', i),
                            'ewk_s' : get_data_fr_yield('fr1s_ewk', i),
                            'qcd_s' : get_data_fr_yield('fr1s_qcd', i),
                            '123' : get_data_fr_yield('fr123en1_qcd', i),
                            '123en' : get_data_fr_yield('fr123en', i),
                        }
                        fake2 = {
                            'en' : get_data_fr_yield('fr2en', i),
                            'ewk_s' : get_data_fr_yield('fr2s_ewk', i),
                            'qcd_s' : get_data_fr_yield('fr2s_qcd', i),
                            '123' : get_data_fr_yield('fr123en2_qcd', i),
                            '123en' : get_data_fr_yield('fr123en', i),
                        }
                        doubles = get_data_fr_yield('fr12s_qcd', i)
                        doubles_en = get_data_fr_yield('fr12en', i)
                        total_yield = estimate_fake_sum(
                            fake1, fake2, doubles, doubles_en)
                        all_fakes.SetBinContent(
                            i, max(0, total_yield.nominal_value))
                        all_fakes.SetBinError(i, total_yield.std_dev())
                    #all_fakes.Draw('pe')

                    legend = ROOT.TLegend(0.6, 0.6, 0.9, 0.90, "", "brNDC")
                    legend.SetFillStyle(0)
                    stack = ROOT.THStack("FR_FINAL",
                                         "Final #mu#mu#tau selection")
                    for histo_name, histo in zip(corrected_mc,
                                                 corrected_mc_histos):
                        stack.Add(histo.th1, 'hist')
                        legend.AddEntry(histo.th1, histo_name, 'lf')
                    stack.Add(all_fakes.th1, 'hist')
                    legend.AddEntry(all_fakes.th1, "Fakes", "lf")
                    stack.Draw()

                    ############################################################
                    ### Make a nice error band of the fake estimate       ######
                    ############################################################

                    error_band_hist = all_fakes + \
                            corrected_mc_histos[0] + corrected_mc_histos[1]
                    # Copy only errors from fake rate
                    for i in range(0, data_fr2s_ewk.GetNbinsX()+2):
                        error_band_hist.SetBinError(i, all_fakes.GetBinError(i))

                    error_band_hist.SetLineColor(ROOT.EColor.kBlack)
                    error_band_hist.SetFillColor(
                        samplestyles.SAMPLE_STYLES['fake_error']['color'].code
                    )
                    error_band_hist.SetFillStyle(1001)
                    error_band_hist.SetMarkerSize(0)
                    legend.AddEntry(error_band_hist.th1, "Fake error", "lf")
                    error_band_hist.DrawCopy('same,e2')
                    error_band_hist.SetFillStyle(0)
                    error_band_hist.Draw('same,hist')
                    ult_data.Draw('pe,same,x0')
                    stack.SetMaximum(2.*max(
                            stack.GetHistogram().GetMaximum(),
                            ult_data.GetMaximum()))

                    signalx5 = signal*5
                    signalx5.SetLineStyle(1)
                    signalx5.SetLineWidth(2)
                    signalx5.SetLineColor(ROOT.EColor.kRed)
                    signalx5.SetFillStyle(0)
                    signalx5.Draw('same, hist')
                    legend.AddEntry(signalx5.th1, "VH(125) #times 5 ", "lf")
                    legend.Draw()

                    saveplot(plot_base_name + '_ult_combfks')

                    ############################################################
                    ### Now save the results in a root file for limits    ######
                    ############################################################
                    # We make a different output for each higgs mass
                    for mass in [100, 110, 115, 120, 125, 135, 140, 145, 160]:
                        # Set the correct name for everything
                        ult_data.SetName('data_obs')
                        corrected_mc_histos[0].SetName('zz')
                        corrected_mc_histos[1].SetName('wz')
                        all_fakes.SetName('fakes')
                        signal = plotter.get_histogram(
                            'VH%i' % mass,
                            ntuple + ':' + plot_base_name + '_ult',
                            rebin = rebin, show_overflows = True
                        )
                        signal.SetName('signal')
                        # Make the output TDirectory
                        output_dir = shape_file.mkdir('_'.join(
                            [channel, charge_cat, str(mass), var]
                        ))
                        # Write everything to the output directory
                        output_dir.cd()
                        ult_data.Write()
                        corrected_mc_histos[0].Write()
                        corrected_mc_histos[1].Write()
                        all_fakes.Write()
                        signal.Write()