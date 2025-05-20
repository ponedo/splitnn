WORK_DIR=$(dirname $(readlink -f $0))
logfile=$1

python3 ${WORK_DIR}/plot_outlier_acc_time.py ${logfile} --lower-percentage 40 --upper-percentage 30

cd - > /dev/null
