# Copyright(c) 2016, The f-scLVM developers (Florian Buettner, Oliver Stegle)
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

# fscLVM
# factorial single cell latent variable model
# this class implements  a  variational inference procedure for a sparse model with different observation noise models.

from .bayesnet.vbfa import *
import scipy as SP
from sklearn import metrics
from sklearn.linear_model import LinearRegression
import re
from sklearn.decomposition import PCA



class CNodeAlphasparse(AGammaNode):
    def __init__(self,net,prior=[1E-3,1E-3]):
        AGammaNode.__init__(self,dim=[net.components],prior=prior)
        
    def update(self,net):
        pass

class CNodeEpsSparse(CNodeEps):
    """Extensions of CNodeEps that can handle fixed prior expectaitons"""
    def __init__(self,net,prior=S.array([100,1])):
            CNodeEps.__init__(self,net,prior)

    def update(self,net):
        pass


class CNodeSsparse(AVGaussNode):
    def __init__(self,net,prec=1):
#        CNodeS.__init__(self,net,prec=1)
        AVGaussNode.__init__(self,dim=[net._N,net.components],cdim=1)
        self.diagSigmaS = SP.ones((net._N,net.components))

    def update(self,net=None):
        pass

class CNodeWsparse(CNodeW):
    """Abstract CnodeWsparse basclass"""
    def __init__(self,net,**kwargin):
        #call base class initialisation
        #CNodeW.__init__(self,net,**kwargin)
        self.Pi = zeros([net.Pi.shape[0],net.Pi.shape[1],2])
        self.Pi[:,:,0] =net.Pi
        self.Pi[:,:,1] = 1.-net.Pi

        self.C    = self.Pi.copy()
        self.Ilabel = SP.arange(net.components)

    def update(self,net=None):
        pass



        
class CNodeWsparseVEM(CNodeWsparse):
    def __init__(self,net,prec=1.):
        CNodeWsparse.__init__(self,net,prec=prec)
        #variable initialisation in CNodeWsparse
        self.sigma2 = (1.0/prec)*SP.ones((net._D, net.components))
        self.E1 = SP.randn(net._D, net.components)
        self.E2diag = SP.zeros((net._D, net.components))
#        for d in range(net._D):
#            self.E2diag[d,:] = SP.diag(self.E2[d,:,:])

    def update(self,net=None):
        pass


class CSparseFA(AExpressionModule):
    '''Variational Bayesian Factor analysis module. `AExpressionModule` is definded in bayesnet.expressionnet'''

    def getDefaultParameters(self):
        """return a hash with default parameter value for this model"""
        dp = AExpressionModule.getDefaultParameters(self)
        return dp

    def getName(self,base_name='fscLVM'):
        """return a name summarising the  main parameters"""

        name = "%s_unannotated_%s_unannotated-sparse_%s_it_%s" % (base_name,self.nLatent,self.nLatentSparse, self.iterationCount)
        return name

    def getF(self):
        """Get imputed expression values

        """        
        isExpressed = (self.Z.E1>0)*1.
        F = self.Z.E1.copy() 
        epsK = self.Eps.E1.copy()
        epsK[self.Eps>1/4.]=1/4.
        Xi = SP.dot(self.S,(self.W.C[:,:,0]*self.W).transpose())
        F[isExpressed==0] = (Xi - (1./(1.+SP.exp(-Xi)))/epsK)[isExpressed==0]
        return F        

    def getRelevance(self):
        """Get posterior relevance (inverse of ARD score) :math:`1/Q(\textbf{\alpha)}`

        """        
        return 1./self.Alpha.E1


    def getTerms(self,annotated=True,unannotated=True,unannotated_sparse=True):
        """Get terms

        """     
        terms = list()
        if unannotated_sparse==True:
            terms.extend(self.terms[self.iLatentSparse])

        if unannotated==True:
            terms.extend(self.terms[self.iLatent])

        if annotated==True:
            terms.extend(self.terms[SP.setxor1d(SP.hstack([SP.where(self.terms=='bias')[0],self.iLatentSparse, self.iLatent]), SP.arange(len(self.terms)))])

        return terms

    def getTermIndex(self,terms):
        """get term index. Creates an index list based on a list of named terms
            Args:
                terms             (list): list with terms
        """
        index=SP.array([list(self.terms).index(id_i) for id_i in terms])
        return index

    def getAnnotations(self, terms=None):
        """Get annotations.

            Args: 
                term        (str): optional list of terms for which annotations are returned. Default None=all terms.
        """      

        if terms is None:
            return (self.Pi>.5)
        else:
            #subset terms
            term_index = self.getTermIndex(terms)
            return (self.Pi[:,term_index]>.5)


    def getW(self,terms=None):
        """Get weights (continous part of spike-and-slab prior) :math:`Q(\widetilde{W})`
            Args:
                term        (str): optional list of terms for which weights are returned. Default None=all terms.


        """        
        if terms is None:
            return self.W.E1 
        else:
            #subset terms
            term_index = self.getTermIndex(terms)
            return self.W.E1[:,term_index]                                        

    def getZ(self,terms=None):
        """Get posterior of Z (Bernourlli part part of spike-and-slab prior) :math:`Q(Z)`
            Args:
                term        (str): optional list of terms for which weights are returned. Default None=all terms.
        """        
        if terms is None:
            return self.W.C[:,:,0]                   
        else:
            term_index = self.getTermIndex(terms)
            return self.W.C[:,term_index,0]                   

    def getPi(self,terms=None):
        """Get prior on Z (Bernourlli part part of spike-and-slab prior)
            Args:
                term        (str): optional list of terms for which weights are returned. Default None=all terms.
        """        
        if terms is None:
            return self.Pi
        else:
            term_index = self.getTermIndex(terms)
            return self.Pi[:,term_index]

    def getZchanged(self,terms=None, threshold=0.5):
        """get matrix indicating whether the posterior distribution has changed for individual terms/genes
            Args:
                terms        (str): optional list of terms for which weights are returned. Default None=all terms.
            Rv:
                matrix [0,-1,1]: 0: no change, -1: loss, +1: gain
        """
        Z = self.getZ(terms)
        Pi = self.getPi(terms)
        I = SP.zeros([Z.shape[0],Z.shape[1]],dtype='int8')
        Igain = (Z>threshold) & (Pi<threshold)
        Iloss = (Z<threshold) & (Pi>threshold)
        I[Igain] = 1
        I[Iloss] = -1
        return I

 
    def getX(self, terms=None):
        """Get factors 

            Args:
                terms        (str): optional list of terms for which weights are returned. Default None=all terms.

        """        
        if terms==None or terms=='all':
            #idxAnno = SP.setxor1d(SP.arange(len(self.terms)), SP.hstack([self.iLatent, self.iLatentSparse]))
            return self.S.E1#[:,idxAnno]
        else:
            idx=self.getTermIndex(terms)
            return self.S.E1[:,idx]



    def regressOut(self,idx=None, terms=None,use_latent=False, use_lm = False, Yraw = None):
        """Regress out unwanted variation

        Args:
            idx          (vector_like): Indices of factors to be regressed out
            use_latent     (bool):      Boolean varoable indicating whether to regress out 
                                        the unwanted variation on the low-dimensional latent 
                                        space or the high-dimensional gene expression space.  
            use_lm               (bool):   Regress out the factors by fitting a linear model for each gene
            Yraw            (array_like): Optionally a gene expression array can be passed from which the facotrs are regressed out                                                         
        Returns:
            A matrix containing the corrected expression values.
        """      

        #if (idx is None) and (terms is None):
        #    raise Exception('Provide either indices or terms to regress out')  

        if terms is None:
            idx = SP.array(idx)  
        else:
            idx = self.getTermIndex(terms)
          
        if use_lm==False and (Yraw is None):  
            isOn =  (self.W.C[:,:,0]>.5)*1.0 
            if use_latent==False: 
                Ycorr = self.Z.E1-SP.dot(self.S.E1[:,idx], (isOn[:,idx]*self.W.E1[:,idx]).T)
            else:
                idx_use = SP.setxor1d(SP.arange(self.S.E1.shape[1]),idx)
                Ycorr = SP.dot(self.S.E1[:,idx_use], (isOn[:,idx_use]*self.W.E1[:,idx_use]).T)    
        else:
            if Yraw is None:
                Y = self.Z.E1.shape
            else:
                Y = Yraw.copy()
            Ycorr = SP.zeros(Y.shape)
            X = self.getX(terms=terms)
            for ig in SP.arange(Y.shape[1]):
                lm = LinearRegression()
                lm.fit(X, Y[:,ig])
                Ycorr[:,ig] = Y-lm.predict(X)

        return Ycorr
             

    def train(self, nIterations=None, forceIterations=False, tolerance=1e-8, minIterations=700):
        """Iterate updates of weights (with spike-and-slab prior), ARD parameters, factors, annd noise parameters.

        Args:
            nIternation          (int): Number of iterations.
            forceIterations     (bool): Force the model to update `nIteration` times. 
            tolerance          (float): Tolerance to monitor convergence of reconstruction error
            minIterations        (int): Minimum number of iterations the model should perform.
                                                          
        """  

        if tolerance is None: tolerance = self.tolerance
        if nIterations is None: nIterations = self.nIterations
        if forceIterations is None: forceIterations = self.forceIterations
        Ion = (self.W.C[:,:,0]>.5)*1.
        Zr = S.dot(self.S.E1,(self.W.E1.T*Ion.T))
        Zd = self.Z.E1-Zr
        error = (abs(Zd)).mean()

        for iter in range(nIterations):
            #t = time.time();
            self.update()
            self.iterationCount+=1
            if SP.mod(iter,100)==0:
                error_old = error.copy()
                Zr = S.dot(self.S.E1,self.W.E1.T)
                Zd = self.Z.E1-Zr
                error = (abs(Zd)).mean()

                print("iteration %i" % iter)

            if (abs(error_old - error) < tolerance) and not forceIterations and iter>minIterations:
                print('Converged after %i iterations' % (iter))
                break

        pass


    def updateS(self,m):
        M = self.components
        if m>=self.nKnown:
            if self.noise=='gauss':
                YmeanX = self.Z.E1
            elif self.noise=='hurdle' or self.noise=='poisson':
                YmeanX = self.meanX

            setMinus = SP.int_(SP.hstack([list(range(M))[0:m],list(range(M))[m+1::]]))

            #update S
            SW_sigma = (self.W.C[:, m,0]*self.W.E1[:, m])*self.Eps.E1
            SW2_sigma = (self.W.C[:, m,0]*(self.W.E2diag[:, m]))*self.Eps.E1              
            setMinus = SP.int_(SP.hstack([list(range(M))[0:m],list(range(M))[m+1::]]))
             
            b0 = SP.dot(self.S.E1[:,setMinus],(self.W.C[:, setMinus,0]*self.W.E1[:, setMinus]).transpose())
            b=SP.dot(b0,SW_sigma)

            alphaSm = SP.sum(SW2_sigma, 0);
            barmuS = SP.dot(YmeanX,SW_sigma) - b
            self.S.diagSigmaS[:,m] = 1./(1 + alphaSm)     
            self.S.E1[:,m] = barmuS/(1. + alphaSm)      
            
            #keep diagSigmaS
            self.Eps.diagSigmaS[m] = SP.sum(self.S.diagSigmaS[:,m])
        else:
            SW2_sigma = (self.W.C[:, m,0]*(self.W.E2diag[:, m]))*self.Eps.E1 
            alphaSm = SP.sum(SW2_sigma, 0)
            self.S.diagSigmaS[:,m] = 1./(1 + alphaSm)   
            
    def updateW(self,m):
        M = self.components
        if self.noise=='gauss':
            YmeanX = self.Z.E1
        elif self.noise=='hurdle' or self.noise=='poisson':
            YmeanX = self.meanX

        if (m<self.nKnown) or (m in self.iLatentSparse) or (m in self.iLatent):
            logPi = SP.log(self.Pi[:,m]/(1-self.Pi[:,m]))            
        elif self.nScale>0 and self.nScale<YmeanX.shape[0]:
            logPi = SP.log(self.Pi[:,m]/(1-self.Pi[:,m]))            
            isOFF_ = self.Pi[:,m]<.5        
            logPi[isOFF_] = (YmeanX.shape[0]/self.nScale)*SP.log(self.Pi[isOFF_,m]/(1-self.Pi[isOFF_,m]))   

            isON_ = self.Pi[:,m]>.5        

            if self.onF>1.:
                logPi[isON_] = self.onF*SP.log(self.Pi[isON_,m]/(1-self.Pi[isON_,m]))

        else:
            onF = 1.
            logPi = SP.log(self.Pi[:,m]/(1-self.Pi[:,m]))  



        sigma2Sigmaw = (1.0/self.Eps.E1)*self.Alpha.E1[m]

                   
        setMinus = SP.int_(SP.hstack([list(range(M))[0:m],list(range(M))[m+1::]]))
        SmTSk = SP.sum( SP.tile(self.S.E1[:,m:m+1],(1, M-1))*self.S.E1[:,setMinus], 0)
        SmTSm = SP.dot(self.S.E1[:,m].transpose(),self.S.E1[:,m]) + self.S.diagSigmaS[:,m].sum()

        b = SP.dot( (self.W.C[:, setMinus,0]*self.W.E1[:, setMinus]),(SmTSk.transpose()))                         
        diff = SP.dot(self.S.E1[:,m].transpose(),YmeanX) - b
        
        SmTSmSig = SmTSm + sigma2Sigmaw
        
        #update C and W 
        
        u_qm = logPi + 0.5*SP.log(sigma2Sigmaw) - 0.5*SP.log(SmTSmSig) + (0.5*self.Eps.E1)*((diff**2)/SmTSmSig)
        self.W.C[:, m,0] = 1./(1+SP.exp(-u_qm))

        self.W.C[:,m,1] = 1-self.W.C[:,m,0]
        self.W.E1[:, m] = (diff/SmTSmSig)                                #q(w_qm | s_qm=1), q=1,...,Q
        self.W.sigma2[:, m] = (1./self.Eps.E1)/SmTSmSig
        self.W.E2diag[:,m] = self.W.E1[:,m]**2 + self.W.sigma2[:,m] 

            
    def updateAlpha(self,m):
            #update Alpha
        Ewdwd = SP.sum(self.W.C[:,m,0]*self.W.E2diag[:,m])
        self.Alpha.a[m] = self.Alpha.pa + 0.5*Ewdwd        
        self.Alpha.b[m] = self.Alpha.pb + SP.sum(self.W.C[:,m,0])/2.0             
        self.Alpha.E1[m] = self.Alpha.b[m]/self.Alpha.a[m]
        
    def updateEps(self):
        #update Eps (vertorised)

        SW_sigma  = self.W.C[:,:,0]*self.W.E1
        SW2_sigma  = self.W.C[:,:,0]*self.W.E2diag
                    
        muSTmuS = SP.dot(self.S.E1.transpose(),self.S.E1)
        muSTmuS0 = muSTmuS - SP.diag(SP.diag(muSTmuS))

        t1 = SP.sum(SW_sigma*SP.dot(self.Z.E1.transpose(),self.S.E1), 1)
        t2 = SP.sum(SW2_sigma*SP.tile(SP.diag(muSTmuS).T + self.Eps.diagSigmaS,(self._D,1)), 1) 
        t3 = SP.sum( SP.dot(SW_sigma,muSTmuS0)*SW_sigma, 1)

        self.Eps.E1 = 1./((self.ZZ  + (-2*t1 + t2 + t3))/self._N) 
        self.Eps.E1[self.Eps.E1>1E6]=1E6

    def updateEpsDrop(self):
        #only consider expressed genes
        SW_sigma  = self.W.C[:,:,0]*self.W.E1
        SW2_sigma  = self.W.C[:,:,0]*self.W.E2diag
        muSTmuS = self.S.E1*self.S.E1  + self.S.diagSigmaS
        muSTmuS = SP.dot(muSTmuS.transpose(),self.isExpressed)
        t1 = SP.sum(SW_sigma*SP.dot(self.Z.E1.transpose(),self.S.E1), 1)
        t2 = SP.sum(SW2_sigma.transpose()* muSTmuS,0)
        t3 = SP.zeros((self._D,))
        mRangeUse =  list(range(SW_sigma.shape[1]))#SP.where(self.doUpdate>=0)[0]
        for m in range(len(mRangeUse)):
            for m1 in mRangeUse[m+1:]:
                tt = ( (self.W.C[:, m1,0]*self.W.E1[:, m1])*SW_sigma[:, m])
                t3 = t3 + tt*SP.dot((self.S.E1[:,m1]*self.S.E1[:,mRangeUse[m]]).transpose(),self.isExpressed)
        self.Eps.E1 = 1./((self.ZZ  + (-2*t1 + t2 + 2*t3))/self.numExpressed)

        self.Eps.E1[self.Eps.E1>1/4.]=1/4.#Bernoulli limit
        self.Eps.E1[self.Eps.E1>1e5]=1e5


    def update(self):
        """ Perform update of weights (with spike-and-slab prior), ARD parameters, factors, annd noise parameters. Called by `iterate` method.                                                          

        """  

        M = self.components
        self.Eps.diagSigmaS = SP.zeros((M,))
        mRange = list(range(M))
        if self.shuffle==True and self.iterationCount>0:
            mRange[self.nKnown:] = SP.random.permutation(mRange[self.nKnown:])
            mRange[self.nKnown:] = SP.random.permutation(mRange[self.nKnown:])
        for m in mRange:
            self.updateW(m)
            self.updateAlpha(m)
            self.updateS(m) 

        if self.noise=='gauss':
            self.updateEps()
        elif self.noise=='hurdle':
            self.updateEpsDrop()

        if self.noise=='hurdle' or self.noise=='poisson':
            epsK = self.Eps.E1.copy()#[self.Eps.E1>1/4.]=1/4
            epsK[self.Eps.E1>1/4.]=1/4.
            Xi = SP.dot(self.S.E1,(self.W.C[:, :,0]*self.W.E1).transpose())
            self.meanX[self.isExpressed==0] = (Xi - (1./(1.+SP.exp(-Xi)))/epsK)[self.isExpressed==0]
        elif self.noise=='poisson':
            Xi = SP.dot(self.S.E1,(self.W.C[:, :,0]*self.W.E1).transpose())
            self.meanX = Xi - self.fprime(Xi, self.Z.E1)/SP.repeat(self.kappa[:,SP.newaxis],self._N,1).T

    def getNchanged(self):
        """ Return number of annotations changed by the model (sum of included and exluded genes )
        """
        i_use = SP.setxor1d(SP.arange(self.Pi.shape[1]), SP.hstack([self.iLatentSparse, self.iLatent]))
        nChanged = SP.sum((self.Pi>.5)!=(self.W.C[:,:,0]>.5), 0)[i_use]*1.0
        nChangedRel = nChanged/SP.sum((self.Pi>.5), 0)[i_use]
        return (nChanged, nChangedRel)



    def printDiagnostics(self):
        """ Print diagnostics of the model. If more than 100% of gene annotations are for at least one factor, the model should be re-fitted with sparse unannotated facotrs.
        """
        (nChanged, nChangedRel) = self.getNchanged()
        if nChangedRel.max()<1:
            print('Maximally ', nChangedRel.max()*100.,'% Genes per factor changed.')
        else:
            print('Maximally ', nChangedRel.max()*100.,'% Genes per factor changed. Re-run with sparse annotated factors.')




    def __init__(self,init_data=None,**parameters):
        """create the object"""
        #handle setting of parameters via Bayesnet constructor
        ABayesNet.__init__(self,parameters=parameters)
        #priors for the various components:
        if not hasattr(self, 'priors'):
            self.priors = {}
        if('Alpha' not in self.priors): self.priors['Alpha']={'priors': [1E-3,1E-3]}
        if('Eps' not in self.priors):   self.priors['Eps']={'priors': [1E-3,1E-3]}
        
        self.dataNode=None

        if init_data is not None:
            self.init(init_data)

    def init(self,init_data,Pi=None,terms=None, noise='gauss', init_factors=None, unannotated_id = "hidden"):
        #initialize the model instance"""
        #AGAussNode is defined in ExpresisonNet
        #expr Y ~ N(\mu= expr, \sigma = 0)
        pattern_hidden = re.compile(unannotated_id+'\d')
        pattern_hiddenSparse = re.compile(unannotated_id+"\D*parse"+"\d")

        #pdb.set_trace()

        Ihidden = SP.array([pattern_hidden.match(term) is not None for term in terms])
        IhiddenSparse = SP.array([pattern_hiddenSparse.match(term) is not None for term in terms])


        self.terms=terms
        if not isinstance(init_data,AGaussNode):
            raise Exception("initialization is only possible from a GaussNode")
        self.Z = CNodeZ(node=init_data)

        #datanode hold the data
        self.dataNode = self.Z
        if self.noise=='poisson':
            self.kappa = 1./4.0 + 0.17*self.Z.E1.max(0)

        if self.noise=='hurdle':
            self.meanX = self.Z.E1.copy()
            self.isExpressed = (self.Z.E1>0)*1.
        self.numExpressed = SP.sum(self.Z.E1>0,0)
        
        #known covariates
        if init_factors!=None and 'Known' in init_factors:
            self.nKnown = init_factors['Known'].shape[1]
            self.Known = init_factors['Known']
            assert self.Known.shape[0] == self.Z.E1.shape[0]
            self.nHidden = self.components-self.nKnown
            if 'Intr' in init_factors:
                self.nKnown = init_factors['Known'].shape[1]
                self.Known = init_factors['Known']
                assert self.Known.shape[0] == self._N
                self.nHidden = self.components-self.nKnown

        #mean term/'bias'
        elif terms[0]=='bias':
            Known =SP.ones((self.Z.E1.shape[0],1)) 
            self.nKnown = 1 
            self.nHidden = self.components-self.nKnown  
        else:
            self.nHidden = self.components
            self.nKnown = 0


            
        #set some attributes that we need frequently for the updates, inculuding 
        #number and idx of hidden and sparse hidden terms

        if init_factors is not None and 'iLatent' in init_factors:
            self.iLatent = init_factors['iLatent']
            self.nLatent = len(init_factors['iLatent'])
        else:
            self.iLatent = SP.where(Ihidden==True)[0]
            self.nLatent = len(self.iLatent)

        if init_factors is not None and 'iLatentSparse' in init_factors:
            self.iLatentSparse = init_factors['iLatentSparse']
            self.nLatentSparse= len(init_factors['iLatentSparse'])
        else:
            self.iLatentSparse = SP.where(IhiddenSparse==True)[0]      
            self.nLatentSparse = len(self.iLatentSparse)        
            
        if init_factors!=None and 'onF' in init_factors:
            self.onF = init_factors['onF']
        else:            
            self.onF = self.Z.E1.shape[0]/10000.#self.nScale

        if init_factors!=None and 'initZ' in init_factors:
            self.initZ = init_factors['initZ']
        else:            
            self.initZ = Pi.copy()
            self.initZ[self.initZ<.2] = 0.01
        
        #Pi is likelihood of link for genes x factors
        self.Pi = Pi
        self.Non = (self.Pi>.5).sum(0)
        # set dimensionality of the data
        [self._N, self._D] = self.Z.E1.shape
        self.ZZ = SP.zeros((self._D,))
        for d in range(self._D):
            self.ZZ[d] = SP.sum(self.Z.E1[:,d]*self.Z.E1[:,d], 0)

        if self.Pi is not None:
            assert self.Pi.shape == (self._D,self.components)

            

        self.nodes = {'S':CNodeSsparse(self),'W':CNodeWsparseVEM(self), 'Alpha':CNodeAlphasparse(self,self.priors['Alpha']['priors']),'Eps':CNodeEpsSparse(self,self.priors['Eps']['priors'])}
        for n in list(self.nodes.keys()): setattr(self,n,self.nodes[n])

        #pca initialisation
        Ion = None
        if self.initType == 'pca':
            Ion = random.rand(self.Pi.shape[0],self.Pi.shape[1])<self.Pi
            self.W.C[:,:,0] = self.Pi.copy()
            #self.W.C[:,:,0][self.W.C[:,:,0]<=.2] = .1
            #self.W.C[:,:,0][self.W.C[:,:,0]>=.8] = .9
            for k in range(self.components):
                sv = linalg.svd(self.Z.E1[:,Ion[:,k]], full_matrices = 0);
                [s0,w0] = [sv[0][:,0:1], S.dot(S.diag(sv[1]),sv[2]).T[:,0:1]]
                v = s0.std(axis=0)
                s0 /= v;
                w0 *= v;
                self.S.E1[:,k] = s0.ravel()
                self.W.E1[Ion[:,k],k] = w0.ravel()
                self.W.E1[~Ion[:,k],k]*=self.sigmaOff
                self.S.diagSigmaS[:,k] = 1./2
        if self.initType == 'pcaRand':
            random.seed(222)
            if self.noise == 'hurdle':
                Zstd = self.Z.E1.copy()
                self.meanZ = Zstd.mean(0)
                Zstd-=Zstd.mean(0)
            elif self.noise == 'poisson':
                Zstd = SP.log2(self.Z.E1.astype('float64')+1)
                Zstd -= Zstd.mean(0)
            else:
                Zstd = self.Z.E1
                #Zstd -= Zstd.mean(0)

            Ion = random.rand(self.Pi.shape[0],self.Pi.shape[1])<self.initZ
            self.W.C[:,:,0] = self.initZ
            self.W.C[:,:,0][self.W.C[:,:,0]<=.1] = .1
            self.W.C[:,:,0][self.W.C[:,:,0]>=.9] = .9
            self.W.C[:,:,1] = 1.-self.W.C[:,:,0]
            
            for k in range(self.nHidden):
                k+=self.nKnown
                if Ion[:,k].sum()>5:
                    #pdb.set_trace()
                    pca = PCA(n_components=1, iterated_power=2,svd_solver='randomized')
                    s0 = pca.fit_transform(Zstd[:,Ion[:,k]])
                    self.S.E1[:,k] =(s0[:,0])
                    self.S.E1[:,k] =  self.S.E1[:,k]/self.S.E1[:,k].std()


                else:
                    self.S.E1[:,k] = random.randn(self._N,)

                self.W.E1[:,k] = SP.sqrt(1./self.components)*SP.randn(self._D)
                self.S.diagSigmaS[:,k] = 1./2
            
            if self.nKnown>0:
                for k in SP.arange(self.nKnown):
                    self.W.E1[:,k] = SP.sqrt(1./self.components)*SP.randn(self._D)
                    self.S.diagSigmaS[:,k] = 1./2
                self.S.E1[:,SP.arange(self.nKnown)] =  self.Known
            if self.nLatent>0:
                for iL in self.iLatent:
                    self.S.E1[:,iL] = random.randn(self._N,)

            # if self.nLatentSparse>0:
            #     for iL in self.iLatentSparse:
            #         #self.S.E1[:,iL] = random.randn(self._N,)   
            #         pca = RandomizedPCA(n_components=iL-self.nLatent+1)
            #         s0 = pca.fit_transform(Zstd[:,Ion[:,iL]])
            #         self.S.E1[:,iL] =(s0[:,iL-self.nLatent])
            #         self.S.E1[:,iL] =  self.S.E1[:,iL]/self.S.E1[:,iL].std()

            if self.saveInit==True:
                self.initS = self.S.E1.copy()
                
        elif self.initType == 'greedy':
            self.S.E1 = random.randn(self._N,self.components)
            self.W.E1 = random.randn(self._D,self.components)
            Ion = (self.Pi>0.5)
            self.W.E1[~Ion]*= self.sigmaOff
            for k in range(Ion.shape[1]):
                self.W.E1[Ion[:,k]]*=self.sigmaOn[k]

        elif self.initType == 'prior':
            Ion = random.rand(self.Pi.shape[0],self.Pi.shape[1])<self.Pi
            self.W.E1[~Ion]*=self.sigmaOff
            for k in range(Ion.shape[1]):
                self.W.E1[Ion[:,k],k]*=self.sigmaOn[k]
        elif self.initType == 'on':
            for k in range(Ion.shape[1]):
                self.W.E1[:,k]*=self.sigmaOn[k]
        elif self.initType == 'random':
            for k in range(self.Pi.shape[1]):
                self.S.diagSigmaS[:,k] = 1./2
                self.S.E1[:,k] = SP.randn(self._N)
            self.W.E1 = SP.randn(self._D, self.Pi.shape[1])
            self.W.C[:,:,0] = self.Pi
            self.W.C[:,:,0][self.W.C[:,:,0]<=.2] = .1
            self.W.C[:,:,0][self.W.C[:,:,0]>=.8] = .9
            if self.nKnown>0:
                for k in SP.arange(self.nKnown):
                    self.W.E1[:,k] = SP.sqrt(1./self.components)*SP.randn(self._D)
                    self.S.diagSigmaS[:,k] = 1./2
                self.S.E1[:,SP.arange(self.nKnown)] =  self.Known
            if self.saveInit==True:
                self.initS = self.S.E1.copy()

        elif self.initType == 'data':
            assert ('S' in list(init_factors.keys()))
            assert ('W' in list(init_factors.keys()))
#            Ion = init_factors['Ion']
            Sinit = init_factors['S']
            Winit = init_factors['W']
            self.W.C[:,:,0] = self.Pi
            self.W.C[:,:,0][self.W.C[:,:,0]<=.2] = .1
            self.W.C[:,:,0][self.W.C[:,:,0]>=.8] = .9
            for k in range(self.components):
                self.S.E1[:,k] = Sinit[:,k]
                self.W.E1[:,k] = Winit[:,k]
                self.S.diagSigmaS[:,k] = 1./2

    #calculate the variational bound:
    def calcBound(self):
        print('Currently not implemented ')




    

    
