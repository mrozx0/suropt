"""
This module provides auxiliary functions to handle settings and files writing and loading.

Attributes:
    settings (dict): A shared dictionary of settings accross the framework.
"""

# Import native packages
from collections import Counter
import json
import os
from pathlib import Path
import pickle
from shutil import rmtree, copyfile

def load_json(file):
    """
    Read a JSON file.

    Args:
        file (str): Path and name of the file to be loaded.

    Returns:
        data (dict): The loaded data.
    """
    with open(file+".json","r") as f:
         data = json.load(f)

    return data

def dump_json(file,data):
    """
    Writes a JSON file.

    Args:
        file (str): Path and name of the file to be written.
        data (dict): The data to be saved.
    """
    with open(file+".json","w") as f:
          json.dump(data, f)

def get_input_from_id(problem_id,problem_folder):
    """
    Get filename from problem ID.

    Args:
        problem_id (int): ID of the problem to be solved.
        problem_folder (str): Directory which contains the input files.

    Returns:
        file (str): Path to the input file of the requested ID.
    """
    matching_ids = [name for name in os.listdir(problem_folder) if name.startswith(str(problem_id).zfill(3))]
    if len(matching_ids) == 1:
        file_name = matching_ids[0].replace(".json","")
    elif len(matching_ids) == 0:
        raise Exception(f"Input for ID {problem_id} undefined")
    else:
        raise Exception(f"ID {problem_id} input multiple defined")

    if not (file_name[:3].isdigit() and file_name[3] is "-"):
        raise Exception('Invalid input file name, should start with "XXX-" where XXX is the problem ID')

    file = os.path.join(problem_folder,file_name)

    return file

def check_valid_settings():
    """
    Check if valid settings are used.
    """
    path = os.path.join(settings["root"],"app","config","inputs","valid_settings")
    valid = load_json(path)
    for i in valid.keys():
        for j in valid[i].keys():
            if j in settings[i].keys() and not (settings[i][j] in valid[i][j]):
                raise Exception(f"Invalid setting for {j}, valid keys are: [{', '.join(valid[i][j])}]")

def update_settings(problem_id):
    """
    Updates the shared settings dictionary with the settings specified in the input file.

    Args:
        problem_id (int): ID of the problem to be solved.
    """
    if not len(settings.keys()) == 1:
        keep = settings["root"]
        settings.clear()
        settings["root"] = keep

    # Get filename
    problem_folder = os.path.join(settings["root"],"app","inputs")
    file = get_input_from_id(problem_id,problem_folder)

    # Update
    update_from_json = load_json(file)
    settings.update(update_from_json)

    # Check valid inputs
    check_valid_settings()

    # Add ID
    settings["id"] = problem_id
    restart_check(settings["id"],file)


def restart_check(id_current,file):
    """
    Args:
        id_current (int): ID of the problem to be solved.    
        file (str): Path and name of the current input file.

    Notes:
        For load_surrogate, only checking that the problem name is the same.
    """
    # Overwrite by default
    fresh = True
    
    # List defined problems
    data_folder, all_result_folders = get_results_folders()

    matching_folders = [folder for folder in all_result_folders if folder.startswith(str(id_current).zfill(3))]

    # If ID has already results, decide whether to overwrite
    if len(matching_folders) > 0:
        
        if len(matching_folders) > 1:
            raise Exception("Too many matching folders")
        else:
            path = os.path.join(data_folder,matching_folders[0])
        # Check whether the stored input file is identic
        stored_input_path = os.path.join(path,"input")
        
        new_input = load_json(file)
        stored_input = load_json(stored_input_path)
        
        same_inputs = Counter(new_input) == Counter(stored_input)

        if same_inputs:
            try:
                status = load_json(os.path.join(path,"status"))
            except:
                    ask_to_overwrite(path,id_current,"status file not found")
            else:
                if settings["surrogate"]["surrogate"] is None:
                    ask_to_overwrite(path,id_current,"restarting is not supported for direct optimization")
                elif status["surrogate_trained"]:
                    ask_to_overwrite(path,id_current,"the model is converged")
                else:
                    # Restart
                    ask_to_overwrite(path,id_current,"restarting not implemented yet") ############
        elif settings["surrogate"]["surrogate"] == "load":
            fresh = False
            print("Loading surrogate, no ovewritting")
        else:
            ask_to_overwrite(path,id_current,"the inputs are different")

    # Make workfolder
    settings["folder"] = make_workfolder(file,fresh)

def get_results_folders():
    """
    Retrieves all current results folders.

    Returns:
        data_folder (str): Path to the directory with result folders.
        all_result_folder (list): List of all results folders.
    """
    data_folder = os.path.join(settings["root"],"data")
    all_result_folders = [name for name in next(os.walk(os.path.join(settings["root"],"data")))[1]]
    
    return data_folder, all_result_folders

def make_workfolder(file,fresh):
    """
    Initialize the workdirectory.

    Args:
        file (str): Path and name of the current input file.
        fresh (bool): Whether this is a new problem to be solved.

    Returns:
        folder_path (str): Path to the current results data folder.
    """
    # Setup the folder path
    folder_name = str(settings["id"]).zfill(3) + "-" +  settings["data"]["problem"]
    folder_path = os.path.join(settings["root"],"data",folder_name)
    figures_path = os.path.join(folder_path,"figures")
    logs_path = os.path.join(folder_path,"logs")

    if fresh:
        # Create folder, if not done yet
        Path(folder_path).mkdir(parents=True,exist_ok=True) # parents in fact not needed   
        Path(figures_path).mkdir(parents=True,exist_ok=True) # parents in fact not needed  
        Path(logs_path).mkdir(parents=True,exist_ok=True) # parents in fact not needed
        if settings["surrogate"]["surrogate"].startswith("ann"):
              Path(os.path.join(figures_path,"ann")).mkdir(parents=True,exist_ok=True) # parents in fact not needed  

        # Copy the inputs file
        copyfile(file+".json",os.path.join(folder_path,"input.json"))

    return folder_path

def dump_object(name,*args):
    """
    Pickle dumps the given objects.

    Args:
        name (str): Path and name of the target file.
        args (any): Any object to be pickle dumped.
    """
    file = os.path.join(settings["folder"],"logs",f"{name}_dump.pkl")
    # Saving the objects:
    with open(file, "wb") as f: 
        pickle.dump(args, f)

def load_object(name):
    """
    Loads the pickled object.

    Args:
        name (str): Path and name of the file to load.

    Returns:
        obj (any): The loaded object.
    """
    file = os.path.join(settings["folder"],"logs",f"{name}_dump.pkl")
    # Getting back the objects:
    with open(file, "rb") as f:
        obj = pickle.load(f)

    return obj

def ask_to_overwrite(path,id_current,text):
    """

    Args:
        path (str): Path to the already defined results folder.
        id_current (int): ID of the problem to be solved.    
        text (str): Reason for everwriting.
    """
    # Ask what to do
    while True:
##        response = input(f"ID {id_current} has already results and {text}. Do you want to overwrite results? [y/n]")
        response = "y"
        if response in ["y","n"]:
            overwrite = True if response=="y" else False
            break
        else:
            print("Invalid input")

    # Either remove old folder or abort
    if overwrite:
        rmtree(path)
    else:
        raise Exception(f"ID {id_current} already defined")

# Initialize setting with the path to the root folder
settings = {"root": os.path.split(__file__.split("app")[0])[0]}

