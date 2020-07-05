"""
This is the main module

Notes:
    * It is assumed one problem is run at a time
    * logs are not stored in data due to max path length issues in kerastuner
"""
# Import custom packages
from core import Model,Surrogate,Optimization
from settings import settings,update_settings

def train_surrogate():
    """
    Docstring.
    """    
    # Train surrogate
    if surrogate.retraining and settings["surrogate"]["append_verification"]:
        surrogate.append_verification
    while not surrogate.trained:
        surrogate.sample()
        surrogate.evaluate()
        surrogate.load_results()
        surrogate.train()
        surrogate.surrogate_convergence()

def optimize():
    """
    Docstring.
    """
    # Solve the optimiaztion problem
    optimization.optimize()

    # Verify whether the optimization result agrees with original model
    if build_surrogate:
        optimization.verify()
        
# Choose problem to solve
problem_id = 3

# Initialize the settings
update_settings(problem_id)

# Initialize the model
model = Model() 

# Check computation setup
build_surrogate = bool(settings["surrogate"]["surrogate"])
perform_optimization = bool(settings["optimization"]["algorithm"])

# Perform comupation
if build_surrogate and not perform_optimization:
    surrogate = Surrogate(model)
    train_surrogate()
elif perform_optimization and not build_surrogate:
    optimization = Optimization(model,None)
    optimize()
elif build_surrogate and perform_optimization:
    surrogate = Surrogate(model)
    train_surrogate()
    optimization = Optimization(model,surrogate)
    while not optimization.converged:
        if not surrogate.trained:
            train_surrogate()
        optimize()    
else:
    print("There is nothing to perform within this model")

if build_surrogate:
    surrogate.save()
##    surrogate.plot_response(inputs=[1,2],output=1,constants=[1])
##    surrogate.plot_response(inputs=[3],output=1,constants=[1,1])

input("Ended")



