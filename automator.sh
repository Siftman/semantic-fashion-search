while true; do
    python fashion.py

    if [ $? -eq 0 ]; then
        echo "Script completed successfully, exiting loop."
        break 
    else
        echo "Script crashed. Restarting in 5 seconds..."
        sleep 1
    fi
done