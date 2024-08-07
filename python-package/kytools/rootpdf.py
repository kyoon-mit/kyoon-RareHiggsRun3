"""
rootpdf
=========================================

A module to create, fit, and store PDF models in ROOT.

"""
import os
import ROOT
from datetime import date

################################################################################

class FittingTool:
    """This class provides methods for fitting the model.

    Args:
        YEAR (int): Year of data-taking.
        CAT (str): Category of the analysis.
        VERS (str): Version of the files.
        VARNAME (str): Name of the variable to fit.
        VARTITLE (str): Title of the variable to fit.
        VARLOW (float): Low range of the variable.
        VARHIGH (float): High range of the variable.

    Raises:
        TypeError: If the value provided for YEAR is not an integer.
        TypeError: If the value provided for VERS is not a string.
        TypeError: If the value provided for CAT is not a string.
        TypeError: If the value provided for VARNAME is not a string.
        TypeError: If the value provided for VARTITLE is not a string.
        TypeError: If the value provided for VARLOW is not a number.
        TypeError: If the value provided for VARHIGH is not a number.
        ValueError: If VARLOW is not smaller than VARHIGH.
    """
    def __init__(self, YEAR, CAT, VERS, VARNAME, VARTITLE, VARLOW, VARHIGH):
        if not type(YEAR) is int: raise TypeError('YEAR must be an integer.')
        if not type(CAT) is str: raise TypeError('CAT must be a string.')
        if not type(VERS) is str: raise TypeError('VERS must be a string.')
        if not type(VARNAME) is str: raise TypeError('VARNAME must be a string.')
        if not type(VARTITLE) is str: raise TypeError('VARTITLE must be a string.')
        if not isinstance(VARLOW, (int, float)): raise TypeError('VARLOW must be a float or int.')
        if not isinstance(VARLOW, (int, float)): raise TypeError('VARHIGH must be a float or int.')
        if not VARLOW < VARHIGH: raise ValueError('VARLOW must be smaller than VARHIGH.')

        self.YEAR, self.CAT, self.VERSION, self.VARNAME, self.VARTITLE, self.VARLOW, self.VARHIGH =\
            YEAR, CAT, VERS, VARNAME, VARTITLE, VARLOW, VARHIGH

        self.x = ROOT.RooRealVar(VARNAME, VARTITLE, VARLOW, VARHIGH)

        today = date.today()
        self._date = f'{today.year}{today.month:02}{today.day:02}'
        self._anpath = 'JPsiCC'
        self._plotsavedir = os.path.join(os.environ['HRARE_DIR'], self._anpath, 'plots', f'v{self.VERSION}', self._date, CAT)
        self._sfx = f'{self.YEAR}_{self.CAT}_v{self.VERSION}_{self._date}'
        self._varsfx = f'{self.YEAR}_{self.CAT}'
        self._pdfkeys = {'sig_gaussian': f'sig_gaussian_{self._varsfx}',
                         # sig_crystalball, ...
                         'bkg_gaussian': f'bkg_gaussian_{self._varsfx}'}

        self.signalPDF = None
        self.MCSIG, self.MCBKG, self.DATABKG = None, None, None
        self.ws_name = f'workspace_{self._sfx}'
        self.w = ROOT.RooWorkspace(self.ws_name, self.ws_name)

        self._vars, self._pdfs, self._data = {}, {}, {}
        self._pdfs = {}

        # Color scheme: http://arxiv.org/pdf/2107.02270
        self._orange = ROOT.kOrange + 1
        self._blue = ROOT.kAzure - 4
        self._trueblue = ROOT.kBlue
        self._red = ROOT.kRed - 4
        self._purple = ROOT.kMagenta - 5
        self._gray = ROOT.kGray + 1
        self._violet = ROOT.kViolet + 2

        print('{}kytools: You have created an instance of rootpdf.FittingTool.{}'.format('\033[1;34m', '\033[0m'))

    def makeSignalPDF(self, pdf_type):
        """Create a signal PDF to this class.

        Args:
            pdf_type (str): PDF type.
        
        Raises:
            ValueError: If the value provided for pdf_type is not a valid option.

        Returns:
            (None)
        """
        mean, stddev, range, low, high =\
            (self.VARLOW+self.VARHIGH)/2, (self.VARHIGH-self.VARLOW)/10, (self.VARHIGH-self.VARLOW), self.VARLOW, self.VARHIGH
        match pdf_type:
            case 'gaussian':
                pdf_name, mu_name, sigma_name = self._pdfkeys[f'sig_{pdf_type}'],\
                    f'sig_gauss_mu_{self._varsfx}', f'sig_gauss_sigma_{self._varsfx}'
                self._vars[mu_name] = ROOT.RooRealVar(mu_name, mu_name, mean, low, high)
                self._vars[sigma_name] = ROOT.RooRealVar(sigma_name, sigma_name, stddev, 1e-2, range/2)
                self._pdfs[pdf_name] = ROOT.RooGaussian(pdf_name, pdf_name, self.x, self._vars[mu_name], self._vars[sigma_name])
                print ('{}kytools: Imported contents into RooWorkspace {}.{}'.format('\033[1;36m', self.ws_name, '\033[0m'))
            case _:
                raise ValueError(f'pdf_type={pdf_type} is not a valid option.')
        print ('{}kytools: Created a signal PDF ----> {}.{}'.format('\033[0;32m', pdf_name, '\033[0m'))
        return

    def makeBackgroundPDF(self, pdf_type):
        """Create a background PDF to this class.

        Args:
            pdf_type (str): PDF type.
        
        Raises:
            ValueError: If the value provided for pdf_type is not a valid option.

        Returns:
            (None)
        """
        mean, stddev, range, low, high =\
            (self.VARLOW+self.VARHIGH)/2, (self.VARHIGH-self.VARLOW)/10, (self.VARHIGH-self.VARLOW), self.VARLOW, self.VARHIGH
        match pdf_type:
            case 'gaussian':
                pdf_name, mu_name, sigma_name = self._pdfkeys[f'bkg_{pdf_type}'],\
                    f'bkg_gauss_mu_{self._varsfx}', f'bkg_gauss_sigma_{self._varsfx}'
                self._vars[mu_name] = ROOT.RooRealVar(mu_name, mu_name, mean, low, high)
                self._vars[sigma_name] = ROOT.RooRealVar(sigma_name, sigma_name, stddev, 1e-2, range/2)
                self._pdfs[pdf_name] = ROOT.RooGaussian(pdf_name, pdf_name, self.x, self._vars[mu_name], self._vars[sigma_name])
                print ('{}kytools: Imported contents into RooWorkspace {}.{}'.format('\033[1;36m', self.ws_name, '\033[0m'))
            case _:
                raise ValueError(f'pdf_type={pdf_type} is not a valid option.')
        print ('{}kytools: Created a background PDF ----> {}.{}'.format('\033[0;32m', pdf_name, '\033[0m'))
        return
    
    def loadRooDataSet(self, rdf, samp):
        """Load RDF as a RooDataSet.

        Args:
            rdf (ROOT.RDataFrame): RDF object containing the data.
            samp (str): Either one of the following options.
                'MC_SIG', 'MC_BKG0', 'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG'
        
        Raises:
            KeyError: If the VARNAME provided for __init__ does not match any column in the RDF.
            ValueError: If the string provided for samp is not among the options.

        Returns:
            (None)
        """
        if self.VARNAME not in rdf.GetColumnNames():
            raise KeyError(f'The VARNAME={self.VARNAME} provided for __init__ does not match any column in the RDF.')
        if samp in ['MC_SIG', 'MC_BKG0', 'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG']:
            dataset_name = f'RooDataSet_{samp}_{self.YEAR}_{self.CAT}'
        else: raise ValueError(f'samp={samp} is not a valid option.')
        rdsMaker = ROOT.std.move(ROOT.RooDataSetHelper(dataset_name, dataset_name, ROOT.RooArgSet(self.x)))
        roo_data_set_result = rdf.Book(rdsMaker, (self.VARNAME,))
        self._data[dataset_name] = roo_data_set_result.GetValue()
        return

    def loadRooDataHist(self, rdf, samp):
        """Load RDF as a RooDataHist.

        Args:
            rdf (ROOT.RDataFrame): RDF object containing the data.
            samp (str): Either one of the following options.
                'MC_SIG', 'MC_BKG0',  'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG'
        
        Raises:
            KeyError: If the VARNAME provided for __init__ does not match any column in the RDF.
            ValueError: If the string provided for samp is not among the options.

        Returns:
            (None)
        """
        if self.VARNAME not in rdf.GetColumnNames():
            raise KeyError(f'The VARNAME={self.VARNAME} provided for __init__ does not match any column in the RDF.')
        if samp in ['MC_SIG', 'MC_BKG0', 'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG']:
            datahist_name = f'RooDataHist_{samp}_{self.YEAR}_{self.CAT}'
        else: raise ValueError(f'samp={samp} is not a valid option.')
        rdhMaker = ROOT.RooDataHistHelper(datahist_name, datahist_name, ROOT.RooArgSet(self.x))
        roo_data_hist_result = rdf.Book(ROOT.std.move(rdhMaker), (self.VARNAME,))
        self._data[datahist_name] = roo_data_hist_result.GetValue()
        return

    def fit(self, samp, pdf_type, binned=True, strategy=2, max_tries=10):
        """
        Args:
            samp (str): One of the following options.
                'MC_SIG', 'MC_BKG0', 'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG'
            pdf_type (str): PDF type.
            binned (bool, optional): Whether to do binned likelihood fitting.
                Defaults to True.
            strategy (int, optional): RooFit fitting strategy. See RooFit documentation.
                Defaults to 2.
            max_tries (int, optional): Number of max tries to reach. Defaults to 10.

        Raises:
            ValueError: If the string provided for samp is not among the options. 
            KeyError: If a PDF corresponding to the pdf_type does not exist.
            KeyError: If the given options do not correspond to an existing data.

        Returns:
            status (int): The status code returned by RooFit.
        """
        if samp not in ['MC_SIG', 'MC_BKG0', 'MC_BKG1', 'MC_BKG2', 'MC_BKG3', 'DATA_BKG']:
            raise ValueError(f'samp={samp} is not a valid option.')
        if binned: datakey_pfx = 'RooDataHist'
        else: datakey_pfx = 'RooDataSet'
        if 'BKG' in samp: data_type = 'bkg'
        else: data_type = 'sig'
        pdfkey = self._pdfkeys[f'{data_type}_{pdf_type}']
        datakey = f'{datakey_pfx}_{samp}_{self.YEAR}_{self.CAT}'
        
        if pdfkey in list(self._pdfs.keys()): pdf = self._pdfs[pdfkey]
        else: raise KeyError(f'You have not created a {data_type} PDF of pdf_type={pdf_type} yet.')
        if datakey in list(self._data.keys()): data = self._data[datakey]
        else: raise KeyError(f'{datakey} does not exist. Please check your options and try again.')

        params = pdf.getParameters(0)
        status = -1
        print ('{}kytools: Performing likelihood fit of {} to {}.{}'.format('\033[1;36m', pdf.GetTitle(), data.GetTitle(), '\033[0m'))
        for ntries in range(1, max_tries+1):
            print ('{}kytools: Fit trial #{}.{}'.format('\033[1;36m', ntries, '\033[0m'))
            fit_result = pdf.fitTo(data,
                                   ROOT.RooFit.Save(True),
                                   ROOT.RooFit.Minimizer('Minuit2', 'minimize'),
                                   ROOT.RooFit.Strategy(strategy),
                                   ROOT.RooFit.PrintLevel(-1),
                                   ROOT.RooFit.Warnings(False),
                                   ROOT.RooFit.PrintEvalErrors(-1))
            status = fit_result.status()
            if (status != 0):                                                                                                                              
                params.assignValueOnly(fit_result.randomizePars())                                                                                                                              
                ntries += 1
            else:
                break
        print ('{}kytools: Likelihood fit has exited with status {}.{}'.format('\033[1;36m', status, '\033[0m'))
        match status:
            case 0:
                print ('{}         Likelihood fit has converged.{}'.format('\033[1;36m', '\033[0m'))
            case 1:
                print ('{}         Covariance was made positive definite.{}'.format('\033[1;36m', '\033[0m'))
            case 2:
                print ('{}         Hessian is invalid.{}'.format('\033[1;36m', '\033[0m'))
            case 3:
                print ('{}         EDM is above max.{}'.format('\033[1;36m', '\033[0m'))
            case 4:
                print ('{}         Reached call limit.{}'.format('\033[1;36m', '\033[0m'))
            case 5:
                print ('{}         Please investigate.{}'.format('\033[1;36m', '\033[0m'))
            case _:
                print ('{}         DISASTER!{}'.format('\033[1;36m', '\033[0m'))
        return status

    def plot(self, mask=[], fwhm=False):
        """Plot.

        Args:
            fwhm (bool, optional): Whether to draw lines indicating FWHM of the signal.
                Defaults to False.
            mask (list(str), optional): Histograms to mask.
                Defaults to [].

        Raises:
            TypeError: If the argument provided for maks is not a list of str.

        Returns:
            (None)
        """
        if not all(isinstance(mask_item, str) for mask_item in mask):
            raise TypeError('Please provide a list(str) for mask.')
        xframe = self.x.frame(Name=self.VARNAME, Title=self.VARTITLE, Bins=int(self.VARHIGH-self.VARLOW))
        for key, dat in self._data.items():
            if any(mask_item in key for mask_item in mask):
                continue
                # dat.plotOn(xframe, DataError=None, XErrorSize=0, FillColor=ROOT.kWhite, LineColor=ROOT.kWhite, MarkerColor=ROOT.kWhite, MoveToBack=True)
            elif 'MC_BKG0' in key: dat.plotOn(xframe, DrawOption='B', DataError=None, XErrorSize=0, FillColor=ROOT.kWhite)
            elif 'MC_BKG1' in key: dat.plotOn(xframe, DrawOption='B', DataError=None, XErrorSize=0, FillColor=self._red)
            elif 'MC_BKG2' in key: dat.plotOn(xframe, DrawOption='B', DataError=None, XErrorSize=0, FillColor=self._orange)
            elif 'MC_BKG3' in key: dat.plotOn(xframe, DrawOption='B', DataError=None, XErrorSize=0, FillColor=self._gray)
            elif 'DATA' in key: dat.plotOn(xframe, DrawOption='P')
        for key, pdf in self._pdfs.items():
            if any(mask_item in key for mask_item in mask): continue
            if 'bkg' in key: pdf.plotOn(xframe, LineColor=ROOT.kBlack, LineStyle=ROOT.kSolid)
            if 'sig' in key: pdf.plotOn(xframe, LineColor=self._blue)
        #TODO: fwhm

        plot_name = f'fitplot_{self._sfx}'
        c = ROOT.TCanvas(plot_name, plot_name, 1000, 1000)
        xframe.Draw()
        c.SaveAs(f'{plot_name}.png')
        print('{}A plot has been created. >> {}.png {}'.format('\033[1;33m', plot_name, '\033[0m'))
        return

    def saveWorkspace(self):
        """Saves all data and pdf to workspace.

        Prints the name of the ROOT file that is created in the current directory.

        Args:
            (None)

        Returns:
            (None)
        """
        for _, var in self._vars.items(): getattr(self.w, 'import')(var)
        for _, pdf in self._pdfs.items(): getattr(self.w, 'import')(pdf)
        for _, dat in self._data.items(): getattr(self.w, 'import')(dat)
        print ('{}kytools: Saving RooWorkspace {} to {}.root...{}'.format('\033[1;36m', self.ws_name, self.ws_name, '\033[0m'))
        self.w.writeToFile(f'{self.ws_name}.root')
        self.w.Print()
        print ('{}kytools: Successfully saved {}{}'.format('\033[1;36m', self.ws_name, '\033[0m'))