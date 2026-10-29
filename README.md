# Лабораторна №2 — MPI моделювання теплоперенесення на STL-меші

Проєкт моделює дифузію тепла між сусідніми трикутними полігонами поверхні STL. Температура є атрибутом полігона; два полігони взаємодіють, коли мають спільне ребро. Меш розділяється між MPI-процесами, а на кожному часовому кроці передаються температури лише граничних (ghost) полігонів.

## Режими вимірювання

Benchmark вимірює кожен етап окремо: `load` (читання STL і геометрія), `adjacency` (граф спільних ребер), `partition` (просторовий MPI-розподіл) та `simulation` (часові кроки теплообміну). Режим `all` лишається для цілісного запуску моделі. Приклад: `scripts/benchmark.bash --mesh /shared/lab2-mesh-heat/data/input/stanford_dragon_120k.stl --steps 300 --repetitions 3`.

Для великої геометрії використано Stanford Dragon: оригінальний PLY містить 871\,414 граней, а `local/prepare_dragon.py` зменшує його до приблизно 120\,000 граней для 2 GB worker. Джерело: Stanford 3D Scanning Repository (розповсюджено через репозиторій `hughsk/stanford-dragon`).

## Модель

Для полігона `i` виконується явна схема:

`T_i(next) = T_i + dt / C_i * sum(K_ij * (T_j - T_i))`.

`C_i = rho * c * thickness * area_i`, а `K_ij = conductivity * shared_edge_length / centroid_distance`. Зовнішні ребра є теплоізольованими. Один центральний полігон є фіксованим джерелом температури; його можна задати через `--hot-face`.

Часовий крок автоматично обмежується умовою стійкості явної схеми. Якщо задано `--dt`, значення, більше за межу стійкості, завершує програму з помилкою.

## Підготовка

На controller має бути Python 3, MPI, а також сумісний з MPI пакет `mpi4py`:

```bash
cd /shared/lab2-mesh-heat
python3 -m pip install --user -r requirements.txt
scripts/prepare_mesh.bash --resolution 100
```

`prepare_mesh.bash` генерує тестову криву пластину на 20 000 трикутників. Для власної моделі скопіюйте STL із маніфолдними трикутними гранями у `data/input/` і передайте його шлях опцією `--mesh` у `run_experiment.bash`.

## Локальна перевірка

```bash
mpiexec -n 1 python3 src/heat_mpi.py --mesh data/input/plate.stl --output-dir results/local-n1 --steps 100
mpiexec -n 2 python3 src/heat_mpi.py --mesh data/input/plate.stl --output-dir results/local-n2 --steps 100
scripts/validate.bash results/local-n1 results/local-n2
```

Перевірка порівнює фінальні температури для однакової моделі та кількості кроків. Результати мають збігатися в межах чисельної похибки.

## Запуск у Slurm

На Windows розгорніть проєкт так само, як у Lab1:

```powershell
cd D:\CSC\6th\S1\CC\Lab2
.\windows\deploy.ps1
```

Після входу на controller:

```bash
cd /shared/lab2-mesh-heat
scripts/prepare_mesh.bash --resolution 100
scripts/run_experiment.bash --nodes 2 --steps 1000 --tag test
scripts/benchmark.bash --steps 1000 --repetitions 3
scripts/export_metrics.bash
```

Для benchmark не запускайте одночасно інші вимірювання на тих самих worker. Після `windows/deploy.ps1 -ExportResults` локально виконайте:

```powershell
py -m pip install -r local\requirements.txt
py local\analyze_results.py D:\Lab2-results
py local\visualize_state.py D:\Lab2-results\raw\RUN_ID\final_state.npz
```

## Дані результату

Кожен запуск створює `final_state.npz` з геометрією та температурою, `summary.csv`, а також `worker/rank-*.csv`. CSV по rank містить кількість власних і ghost-полігонів, кількість межових зв'язків, час обміну та час обчислень. `metrics/runs.csv` містить дані запусків Slurm.

Для звіту PNG можна отримати командою `local/visualize_state.py`; LaTeX-фрагмент для його вставлення зберігається у `report/figures.tex`.

Для інтерактивної візуалізації в ParaView експортуйте поле на сам меш у VTK:

```powershell
py local\export_vtk.py results\full-benchmark\final_state_n4.npz --output results\full-benchmark\export\temperature_n4.vtk
```

У ParaView відкрийте VTK, виберіть `Coloring → temperature` та за потреби застосуйте `Surface With Edges`.
