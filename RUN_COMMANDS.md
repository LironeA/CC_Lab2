# Команди виконання

```powershell
cd D:\CSC\6th\S1\CC\claster
.\cluster.ps1 -Action start
.\cluster.ps1 -Action status
cd D:\CSC\6th\S1\CC\Lab2
.\windows\deploy.ps1
```

```bash
# controller
cd /shared/lab2-mesh-heat
python3 -m pip install --user -r requirements.txt
scripts/prepare_mesh.bash --resolution 100
scripts/run_experiment.bash --nodes 1 --steps 100 --tag validation
scripts/run_experiment.bash --nodes 2 --steps 100 --tag validation
# Pass the two generated run folders to validate.bash.
scripts/benchmark.bash --steps 1000 --repetitions 3
scripts/export_metrics.bash
```
