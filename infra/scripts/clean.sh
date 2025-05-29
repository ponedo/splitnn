rm /tmp/monitor_*
for pid in $(ps aux | grep topo_setup_test | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep bpftrace | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep 'sleep inf' | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep cctr | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep goctr | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep monitor_kern_func | grep -v grep | awk '{print $2}'); do kill -9 $pid; done
for pid in $(ps aux | grep monitor_cpu_mem_usage | grep -v grep | awk '{print $2}'); do kill -9 $pid; done

ip -all netns del all

start=$(($(date +%s%N) / 1000000))
sleep 1
for ((i=0; i<100; i++)); do ip link add test-dummy type dummy; ip link del test-dummy; done
end=$(($(date +%s%N)/1000000))

echo "$((end - start))ms"