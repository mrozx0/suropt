# Import native packages
import os

# Import pypi packages
import numpy as np

# Import custom packages
from core.settings import dump_json, dump_object, load_json, load_object, settings
from datamod import get_data, scale
from datamod.results import make_response_files, append_verification_to_database
from datamod.sampling import determine_samples, resample_static, resample_adaptive
from metamod import cross_validate, optimize_hyperparameters, train_surrogate
from metamod.deploy import get_partial_input
from metamod.performance import check_convergence, retrieve_metric
from visumod import compare_surrogate, correlation_heatmap, plot_raw, sample_size_convergence, surrogate_response

class Surrogate:
    
    def __init__(self,model):

        # Carry over model
        self.model = model

        # Training status
        self.trained = False
        self.hp_optimized = False
        
        # Initialize sampling
        self.no_samples = 0
        self.sampling_iterations = 0

        # Initialize metrics
        self.convergence_metric = {"name":settings["data"]["convergence"],"values":[]}

        # Make response files
        self.file, self.verification_file = make_response_files(settings["folder"],self.model.dim_in,self.model.n_obj,self.model.n_const)

        # Initialize log
        if not settings["surrogate"]["surrogate"] == "load":
            initial_log = {"surrogate_trained":False,"range_in":self.model.range_in.tolist(),"dim_in":self.model.dim_in,"dim_out":self.model.dim_out,"n_const":self.model.n_const}
            dump_json(os.path.join(settings["folder"],"status"),initial_log )
        
    def sample(self):
        """
        Wrapper function to obtrain the new sample points.

        Note:
            - be careful with geometric, grows fast
            - if non-adaptive sampling is used, adaptive must be set to None
        """

        # Track iteration number
        self.sampling_iterations += 1
        print("----------------------------------------")
        print(f"Iteration {self.sampling_iterations}")

        # Determine number of new samples
        no_new_samples = determine_samples(self.no_samples,self.model.dim_in)
        
        # Obtain new samples
        if settings["data"]["evaluator"] == "data":
            self.samples = self.model.evaluator.get_samples(self.no_samples,no_new_samples)
        elif self.no_samples == 0 or not settings["data"]["adaptive"]:
            self.samples = resample_static(no_new_samples,self.no_samples,self.model.range_in)
        else:
            self.samples = resample_adaptive(no_new_samples,self.surrogates,self.data)

        # Update sample count
        self.no_samples += no_new_samples
            
    def evaluate_samples(self,verify=False):
        """
        Wrapper function to call the evaluted problem solver.

        STUFF
        """
        # Select target file
        if verify:
            file = self.verification_file
        else:
            file = self.file

        # Evaluate the samples
        self.model.evaluator.generate_results(self.samples,file,self.sampling_iterations)

    def append_verification(self):
        """
        Add verification results to database.
        """
        append_verification_to_database(self.file,self.verification_file)
        
    def load_results(self,verify=False):
        """
        Wrapper function to load the results from the results file

        Arguments:
            verify: whether this is a verification run

        STUFFs
        """
        if verify:
            self.verification = get_data(self.verification_file)
        else:
            # Read database
            self.data = get_data(self.file)
            # Plot the input data
            plot_raw(self.data,self.sampling_iterations)

    def train(self):
        """
        Wrapper function to (re)train the surrogate.

        STUFF
        """
        if not self.hp_optimized:
            if settings["surrogate"]["surrogate"] == "name" and iteration == 1:
                self.hp_optimized = optimize_hyperparameters(self.data,self.sampling_iterations)
            else:
                self.hp_optimized = True
        
        # Train the surrogates
        self.surrogates = cross_validate(self.data,self.sampling_iterations)

        # Select the best model
        self.surrogate = train_surrogate(self.data)

        # Plot the surrogate response
        compare_surrogate(self.data.input,self.data.output,self.surrogate.predict_values,self.sampling_iterations)

    def check_convergence(self):
        # Determine metrics
        self.surrogate.metric = retrieve_metric(self.surrogates)

        # Append convergence metric
        self.convergence_metric["values"].append(self.surrogate.metric["mean"])

        # Check convergence
        self.trained = check_convergence(self.convergence_metric["values"])

    def report(self):
        sample_size_convergence(self.convergence_metric)
        dump_object("stats",self.convergence_metric["values"],self.sampling_iterations)

        if self.trained:
            print("Surrogate converged")
            # Plot the sample size convergence
            correlation_heatmap(self.surrogate.predict_values,self.model.dim_in)

    def plot_response(self,inputs,output,density=10,**kwargs):
        if len(inputs) > 2:
            raise Exception("Too many input dimensions requested for a plot")

        if not isinstance(output,int):
            raise Exception("Too many output dimensions requested for a plot, should specify an integer")

        if output > self.model.dim_out:
            raise Exception("Output dimension out of bounds")
        
        # Convert to 0 based indexing
        inputs = np.array(inputs) - 1
        output = output - 1

        # Get response        
        input_norm = get_partial_input(density,inputs,self.model.dim_in,self.data.input_abs_max,**kwargs)
        output_norm = self.surrogate.predict_values(input_norm)

        # Unormalize
        input_vec = scale(input_norm,self.model.range_in)
        output_vec = scale(output_norm,self.data.range_out)

        # Make plot
        surrogate_response(input_vec[:,inputs],output_vec[:,[output]],inputs)

    def save(self):
        if self.surrogate.name == 'ANN':
            self.surrogate.model.save(os.path.join(settings["folder"],"logs","ann"))
        else:
            dump_object("meta",self.surrogate)

        status = load_json(os.path.join(settings["folder"],"status"))
        to_update = {"surrogate_trained":True,"range_out":self.surrogate.range_out.tolist()}
        status.update(to_update)
        dump_json(os.path.join(settings["folder"],"status"),status)

    def reload(self):
        status = load_json(os.path.join(settings["folder"],"status"))

        if "ann" in os.listdir(os.path.join(settings["folder"],"logs")):
            from metamod.ANN import ANN ############################################
            from tensorflow.keras.models import load_model as load_keras_model ############################################
            
            interp = ANN()
            interp.nx = status["dim_in"]
            interp.ny = status["dim_out"]
            interp.model = load_keras_model(os.path.join(settings["folder"],"logs","ann"))
            interp.range_out = np.array(status["range_out"])
            interp.options["print_global"] = False
            self.surrogate = interp
        else:
            self.surrogate = load_object("meta")[0]
