# This is a bash script that distributes the workload of transcription to specific lab computers 
# Written by Reishiro

#!/bin/bash

# Time window (24-hour format)
START_HOUR=23   # 11:00 PM
END_HOUR=8      # 8:00 AM

# Function to check if the current time is within the allowed time window or it's a weekend
wait_for_time_window() {
    local current_hour current_day
    while true; do
        current_hour=$(date +"%H")
        current_day=$(date +"%u")  # %u gives day of week (1=Monday, 7=Sunday)

        # Convert to base-10 to avoid octal issues
        current_hour=$((10#$current_hour))
        current_day=$((10#$current_day))
        
        # Check if within the time window or if it's a weekend
        if (( current_day == 6 || current_day == 7 )) || \
           (( (current_hour >= START_HOUR || current_hour < END_HOUR) && (current_day >= 1 && current_day <= 5) )); then
            echo "Allowed time: either in the time window ${START_HOUR}:00 to ${END_HOUR}:00 on weekdays or it's a weekend."
            break
        else
            echo "Current time is outside allowed window and it's a weekday. Waiting..."
            sleep 3600  # Wait for 1 hour before checking again
        fi
    done
}

# Wait for the time window before running
wait_for_time_window

# Define the queue of remote machines
REMOTE_MACHINES=(
    "turkey"
    "starling"
    "hyssop"
    "cinnamon"

    "bacon"
    "mustard"
    "pepper"
    "onion"
    "honey"
    "cream"

    "coconut"
    "cayenne"
    "egg"
    "marjoram"
    "lavender"
    "molasses"
    "olive"
    "cheese"
    "oil"
    "oregano"
    "rosemary"
    "lime"
    "thyme"
    "flour"
    "tomato"
)    

# Path to the Pyhon script to be run on each remote machine
PYTHON_SCRIPT_PATH="/scratch/rkawaka1/dataTranscription_pyannote.py"
# PYTHON_SCRIPT_PATH="/scratch/rkawaka1/projects/podcast-hate-speech/test_Transcription.py"
DIRECTORY_PATH="/scratch/rkawaka1/"

# Path to the FIFO queue file
FIFO_QUEUE="/scratch/rkawaka1/queue"

# Create a FIFO queue
if [[ ! -p ${FIFO_QUEUE}  ]]; then
        mkfifo ${FIFO_QUEUE}
fi

# Initial argument
INITIAL_ARG=7608
# INITIAL_ARG=2
# Increment value
INCREMENT=1
# Counter to keep track of the current argument value
CURRENT_ARG=${INITIAL_ARG}
# Maximum argument value
MAX_ARG=47704
# MAX_ARG=10

# Function to process a single remote machine
process_machine() {
    local remote_machine=$1
    local current_arg=$2
    local increment=${INCREMENT}

    echo "Processing ${remote_machine} with arguments: ${current_arg} and increment: ${increment}"

    ssh -t -o LogLevel=ERROR -o BatchMode=yes ${remote_machine} << EOF
        export PYTHONPATH=
        export WORKON_HOME=~/Envs
        source /usr/local/bin/virtualenvwrapper.sh
        workon ${remote_machine}_venv
        cd ${DIRECTORY_PATH}
        python3 ${PYTHON_SCRIPT_PATH} ${current_arg} ${increment}
        deactivate
    EOF

    echo "Python script completed on ${remote_machine} starting from row ${current_arg} to $((current_arg + increment - 1))."

    # Re-add the machine to the FIFO queue
    echo ${remote_machine} > ${FIFO_QUEUE}
}


# Function to start the initial batch of processes
start_initial_processes() {
    for machine in "${REMOTE_MACHINES[@]}"; do
        # Start the process in the background and pass the machine to the function
        process_machine ${machine} ${CURRENT_ARG} ${INCREMENT} &
        #CURRENT_ARG=$((CURRENT_ARG + INCREMENT))
        CURRENT_ARG=$((CURRENT_ARG + INCREMENT)) 
    done
}

# Start processing the initial batch of machines with arguments
start_initial_processes "$@"

# Continuously read from the FIFO queue and start new processes
while true; do
    if (( CURRENT_ARG > MAX_ARG )); then
        echo "Reached maximum argument value. Exiting."
        exit 0
    fi

    wait_for_time_window

    if read -r next_machine < ${FIFO_QUEUE}; then
        process_machine ${next_machine} ${CURRENT_ARG} ${INCREMENT} &
        # Increment the argument for the next machine
        # CURRENT_ARG=$((CURRENT_ARG + INCREMENT))
        CURRENT_ARG=$((CURRENT_ARG + INCREMENT))

    fi
done


    ## Main Lab (240)
    # "mustard"
    # "cornstarch"
    # "poppy"
    # "spinach"
    # "pepper"
    # "bacon"
    # "onion"
    # "honey"
    # "cream"
    # "cabbage"
    # "nutmeg"
    # "coriander"
    # "mugwort"
    # "cheese"
    # "celery"
    # "oil"
    # "oregano"
    # "rosemary"
    # "thyme"
    # "lime"
    # "flour"
    # "tomato"
    # "sage"
    # "turmeric"
    # "horseradish"    
    # "butter"
    # "caper" 
    # "mace"

    # Overflow
    # "lavender"
    # "egg"
    # "coconut"
    # "olive"
    # "marjoram"

    ## Server room and robot lab
    # "stork"
    # "turkey"
    # "starling"
    # "anise"
    # "ginger"
    
    ## Not Even Lab Machines
    # "perilla"
    # "sumac"
    # "mushroom"
    # "paprika"
    # "phoenix"
