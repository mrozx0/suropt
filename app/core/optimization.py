"""
Module containing the optimization surrogate.

Attributes:
    ref_points (dict): Reference points for benchmark problems.
"""
# Import native packages
import os

# Import pypi packages
import numpy as np

# Import custom packages
from core.settings import settings
from datamod.problems import Custom
from optimod import set_optimization, solve_problem
from optimod.performance import calculate_hypervolume, verify_results
from visumod import compare_pareto_fronts, vis_design_space, vis_objective_space, vis_objective_space_pcp

class Optimization:
    """
    The class to define the optimization problem.
    
    Attributes:
        model (core.Model): The model object.
        iterations (int): Number of optimization iterations.
        converged (bool): Convergence status.
        algorithm (): Optization algorithm object.
        termination (): Termination object.
        n_const (int): NUmber of constraints.
        ref_point (np.array): Reference point for hypervolume calculation.
        direct (bool): Whether a direct optimization is performed.
        range_in (np.array): Input parameter allowable ranges.
        function (): Function used to evaluate the candidates.
        problem (datamod.problems.Custom): Problem object.
        surrogate (core.Surrogate): Surrogate object.
        res (pymoo.model.result.Result): Results object.
        optimization_stats (dict): Optimization benchmark statistics.
        optimum_model (np.array): Candidates evaluated by the original model.
        optimum_surrogate (np.array): Candidates evaluated by the surrogate.
        error_measure  (float): Maximum of the error metrics.
        error (np.array): Benchmark percent error.
    """
    def __init__(self,model):
        """
        Args:
            model (core.Model): The model object.
        """
        self.model = model

        self.iterations = 0
        self.converged = False

        # Obtain optimization setup
        self.algorithm, self.termination = set_optimization(model.n_obj)
        
        # Deactivate constrains if not set otherwise
        if settings["optimization"]["constrained"]:
            self.n_const = self.model.n_const
        else:
            self.n_const = 0
        
        self.direct = not bool(settings["surrogate"]["surrogate"])

        try:
            self.ref_point = np.array(ref_points[settings["data"]["problem"]])
        except:
            self.ref_point = None

    def set_problem(self,surrogate):
        """
        Wrapper function to set the problem.

        Args:
            surrogate (core.Surrogate): Surrogate object.

        Notes:
            Direct optimization does not normalize.
        """
        print("###### Optimization #######")
        self.iterations += 1

        if self.direct:
            # Specify range
            self.range_in = np.array(settings["optimization"]["ranges"])
            self.function = self.model.evaluator.evaluate
        else:
            self.surrogate = surrogate
            self.range_in = self.surrogate.data.range_in
            self.function = self.surrogate.surrogate.predict_values

        self.problem = Custom(self.function,self.range_in.T[0],self.range_in.T[1],self.model.n_obj,self.n_const)

        if not self.direct:
            self.problem.norm_in = self.surrogate.data.norm_in
            self.problem.norm_out = self.surrogate.data.norm_out
        
    def optimize(self):
        """
        Wrapper function to perform optimization.
        """

        self.res = solve_problem(self.problem,self.algorithm,self.termination,self.direct)

        if self.res is not None:
            self.plot_results()

    def plot_results(self):
        """
        Plot the optimized candidates.
        """
        # Plot the optimization result in design space
        vis_design_space(self.res.X,self.iterations)
            
        # Plot the optimization result in objective space
        vis_objective_space(self.res.F,self.iterations)
        if self.model.n_obj > 1:
            vis_objective_space_pcp(self.res.F,self.iterations)

    def benchmark(self):
        """
        Determine the benchmark optimization accuracy.
        """
        ps_calc = self.res.X
        pf_calc = self.res.F
        ps_true = self.model.evaluator.problem.pareto_set()
        pf_true = self.model.evaluator.problem.pareto_front()
        self.optimization_stats = {}
        if not np.all(ps_true==None):
            if self.model.n_obj == 1:
                self.optimization_stats["ps_error"] = 100*(ps_true-ps_calc)/ps_true
        if not np.all(pf_true==None):
            if self.model.n_obj == 1:
                self.optimization_stats["pf_error"] = 100*(pf_true-pf_calc)/pf_true
            else:
                self.optimization_stats["hv_calc"] = calculate_hypervolume(pf_calc,self.ref_point)
                self.optimization_stats["hv_true"] = calculate_hypervolume(pf_true,self.ref_point)
                self.optimization_stats["pf_error"] = 100*(self.optimization_stats["hv_true"]-self.optimization_stats["hv_calc"])/self.optimization_stats["hv_true"]
                if self.model.n_obj == 2:
                    compare_pareto_fronts(pf_true,pf_calc)

        # Output
        if bool(self.optimization_stats):
            path = os.path.join(settings["folder"],"logs","optimization_benchmark.txt")

            with open(path, "w") as file:
                for stat in self.optimization_stats:
                    file.write(f"{stat}: {self.optimization_stats[stat]}")
                    file.write("\n")

    def verify(self):
        """
        Wrapper function to verify the optimized solutions.
        """        
        if self.res is not None:
            # Evaluate randomly selected samples using surrogate
            verificiation_idx = verify_results(self.res.X, self.surrogate)

            # Calculate error
            response_F = self.surrogate.verification.response[:,:-self.problem.n_constr or None]
            self.optimum_model = response_F[-len(verificiation_idx):,:]
            self.optimum_surrogate = self.res.F[verificiation_idx]
            self.error = np.abs((100*(self.optimum_model-self.optimum_surrogate)/self.optimum_model))

            # Evaluate selected measure
            measure = settings["optimization"]["error"]
            if measure == "max":
                measured_error = self.error
            elif measure == "mean":
                measured_error = np.mean(self.error,0)
            elif measure == "percentile":
                measured_error = np.percentile(self.error,60,0,interpolation="lower")

            self.error_measure = np.max(measured_error)

            print(f"Optimization {measure} percent error: {self.error_measure:.2f}")

            self.converged = self.error_measure <= settings["optimization"]["error_limit"]

        else:
            self.converged = False
            
        if self.converged:
            print("\n############ Optimization finished ############")
            print(f"Total number of samples: {self.surrogate.no_samples:.0f}")
        else:
            self.surrogate.trained = False
            if settings["surrogate"]["append_verification"]:
                    self.surrogate.append_verification()

    def report(self):
        """
        Report the optimal solutions and their verification accuracy.
        """
        path = os.path.join(settings["folder"],"logs",f"optimizatoin_iteration_{self.iterations}.txt")

        if self.res is not None:
            with open(path, "a") as file:
                file.write("======= F ========\n")
                np.savetxt(file,self.res.F,fmt='%.6g')
                file.write("\n======= X ========\n")
                np.savetxt(file,self.res.X,fmt='%.6g')
                if not self.direct:
                    file.write("\n======= VERIFICATION ========\n")
                    stats = np.concatenate((self.optimum_model,self.optimum_surrogate),1)
                    np.savetxt(file,stats,fmt='%.6g')
                    file.write("\n======= ERROR ========\n")
                    np.savetxt(file,self.error,fmt='%.6g')
                file.write("\n")


            
        ##len([step["delta_f"] for step in model.res.algorithm.display.term.metrics])

ref_points = {"tnk":[1.2,1.2],"dtlz7":[1,1,7],"osy":[-50,100],"bnh":[150,70]}
