import networkx as nx
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from matplotlib import cm
import math
from pathlib import Path
from tqdm.auto import tqdm
import tarfile
import random

# Scoring constants
MAX_WEIGHT = 1000
MAX_EDGES = 10000
N_SMALL = 100
N_MEDIUM = 300
N_LARGE = 1000
K_EXP = 0.5
K_COEFFICIENT = 100
B_EXP = 70 

INPUT_SIZE_LIMIT = 1000000
OUTPUT_SIZE_LIMIT = 10000


def write_input(G: nx.Graph, path: str, overwrite: bool=False):
    assert overwrite or not os.path.exists(path), \
        'File already exists and overwrite set to False. Move file or set overwrite to True to proceed.'
    if validate_input(G):
        with open(path, 'w') as fp:
            json.dump(nx.node_link_data(G), fp)


def read_input(path: str):
    assert os.path.getsize(path) < INPUT_SIZE_LIMIT, 'This input file is too large'
    with open(path) as fp:
        G = nx.node_link_graph(json.load(fp), multigraph=False)
        if validate_input(G):
            return G


def write_output(G: nx.Graph, path: str, overwrite=False):
    assert overwrite or not os.path.exists(path), \
        'File already exists and overwrite set to False. Move file or set overwrite to True to proceed.'
    if validate_output(G):
        with open(path, 'w') as fp:
            json.dump([G.nodes[v]['team'] for v in range(G.number_of_nodes())], fp)


def read_output(G: nx.Graph, path: str):
    assert os.path.getsize(path) < OUTPUT_SIZE_LIMIT, 'This output file is too large'
    with open(path) as fp:
        l = json.load(fp)
        assert isinstance(l, list), 'Output partition must be a list'
        assert set(G) == set(range(len(l))), 'Output does not match input graph'
        nx.set_node_attributes(G, {v: l[v] for v in G}, 'team')
        if validate_output(G):
            return G


def validate(G: nx.Graph):
    assert not G.is_directed(), 'G should not be directed'
    assert set(G) == set(range(G.number_of_nodes())), 'Nodes must be numbered from 0 to n-1'
    return True


def validate_input(G: nx.Graph):
    for n, d in G.nodes(data=True):
        assert not d, 'Nodes cannot have data'
    for u, v, d in G.edges(data=True):
        assert u != v, 'Edges should be between distinct vertices (a penguin is experiencing inner-conflict)'
        assert set(d) == {'weight'}, 'Edge must only have weight data'
        assert isinstance(d['weight'], int), 'Edge weights must be integers'
        assert d['weight'] > 0, 'Edge weights must be positive'
        assert d['weight'] <= MAX_WEIGHT, f'Edge weights cannot be greater than {MAX_WEIGHT}'
    assert G.number_of_edges() <= MAX_EDGES, 'Graph has too many edges'
    assert sum(d for u, w, d in G.edges(data='weight')) >= MAX_WEIGHT*MAX_EDGES*0.05, \
        f'There must be at least {MAX_WEIGHT*MAX_EDGES*0.05} edge weight in the input.'
    assert not G.is_multigraph()
    return validate(G)


def validate_output(G: nx.Graph):
    for n, d in G.nodes(data=True):
        assert set(d) == {'team'}, 'Nodes must have team data'
        assert isinstance(d['team'], int), 'Team identifier must be an integer'
        assert d['team'] > 0, 'Team identifier must be greater than 0'
        assert d['team'] <= G.number_of_nodes(), 'Team identifier unreasonably large'
    return validate(G)


def score(G: nx.Graph, separated=False):
    output = [G.nodes[v]['team'] for v in range(G.number_of_nodes())]
    teams, counts = np.unique(output, return_counts=True)

    k = np.max(teams)
    b = np.linalg.norm((counts / G.number_of_nodes()) - 1 / k, 2)
    C_w = sum(d for u, v, d in G.edges(data='weight') if output[u] == output[v])

    if separated:
        return C_w, K_COEFFICIENT * math.exp(K_EXP * k), math.exp(B_EXP * b)
    return C_w + K_COEFFICIENT * math.exp(K_EXP * k) + math.exp(B_EXP * b)


def visualize(G: nx.Graph):
    output = G.nodes(data='team', default=0)
    partition = dict()
    for n, t in output:
        if t not in partition:
            partition[t] = []
        partition[t].append(n)

    pos = dict()
    circle_size = len(partition) * 0.5
    for k, v in partition.items():
        pos.update(nx.shell_layout(G, nlist=[v], center=(circle_size*math.cos(math.tau*k / len(partition)),
                                                         circle_size*math.sin(math.tau*k / len(partition)))))

    crossing_edges = [e for e in G.edges(data='weight') if output[e[0]] != output[e[1]]]
    within_edges = [e for e in G.edges(data='weight') if output[e[0]] == output[e[1]]]
    max_weight = max(nx.get_edge_attributes(G, name='weight').values())

    nx.draw_networkx_nodes(G, pos, node_color=[output[n] for n in G],
                           cmap=cm.get_cmap('tab20b'))
    nx.draw_networkx_labels(G, pos, font_size=10, font_color="white")

    nx.draw_networkx_edges(G, pos, edgelist=crossing_edges, edge_color=[x[2] for x in crossing_edges],
                           edge_cmap=cm.get_cmap('Blues'), edge_vmax=max_weight*1.5, edge_vmin=max_weight*-0.2)
    nx.draw_networkx_edges(G, pos, width=2, edgelist=within_edges, edge_color=[x[2] for x in within_edges],
                           edge_cmap=cm.get_cmap('Reds'), edge_vmax=max_weight*1.5, edge_vmin=max_weight*-0.2)

    plt.tight_layout()
    plt.axis("off")
    plt.show()


def run(solver, in_file: str, out_file: str, overwrite: bool=False):
    instance = read_input(in_file)
    output = solver(instance)
    if output:
        instance = output
    write_output(instance, out_file, overwrite)
    print(f"{str(in_file)}: cost", score(instance))


def run_all(solver, in_dir, out_dir, overwrite: bool=False):
    for file in tqdm([x for x in os.listdir(in_dir) if x.endswith('.in')]):
        run(solver, str(Path(in_dir) / file), str(Path(out_dir) / f"{file[:-len('.in')]}.out"), overwrite)


def tar(out_dir, overwrite=False):
    path = f'{os.path.basename(out_dir)}.tar'
    assert overwrite or not os.path.exists(path), \
        'File already exists and overwrite set to False. Move file or set overwrite to True to proceed.'
    with tarfile.open(path, 'w') as fp:
        fp.add(out_dir)

def random_distribution(num_teams, num_nodes):
    """
    Returns a random even distribution with num_teams teams
    """
    team_assignments = []
    i = 0
    j = 1
    while i < num_nodes:
        team_assignments.append(j)
        j = ((j+1) % num_teams) + 1
        i += 1
    random.shuffle(team_assignments)
    return team_assignments

def determine_worst_team(G: nx.Graph, num_teams):
    """
    Returns the number of the worst team (most disputes)
    """
    # index 0 will remain 0 as a placeholder
    team_weights = [0 for i in range(num_teams+1)]
    for u, v, d in G.edges(data='weight'):
        if G.nodes[u]['team'] == G.nodes[v]['team']:
            team_weights[G.nodes[u]['team']] += d
    return team_weights.index(max(team_weights))

def improve_worst_team(input: nx.Graph):
    """
    Returns a version of input where the worst team is broken
    """
    # retrieves the old assignments for G
    new = input.copy()
    old_assignments = []
    for i in range(new.number_of_nodes()):
        old_assignments.append(new.nodes[i]['team'])
    num_teams = max(set(old_assignments))

    # determines the worst team in G
    worst_team = determine_worst_team(new, num_teams)

    # swaps each member of the worst team with a random node in G
    new_assignments = old_assignments.copy()
    for i in range(len(old_assignments)):
        if old_assignments[i] == worst_team:
            swap_index = int(random.random()*len(old_assignments))
            new_assignments[i], new_assignments[swap_index] = new_assignments[swap_index], new_assignments[i]
    
    # assigns the new teams to G
    for i in range(new.number_of_nodes()):
        new.nodes[i]['team'] = new_assignments[i]
    return new

def random_graph(input: nx.Graph, num_teams):
    """
    Returns a copy of input with nodes randomly assigned into num_teams teams
    """
    new_graph = input.copy()

    # assign random teams to the graph
    assignment = random_distribution(num_teams, new_graph.number_of_nodes())
    for i in range(new_graph.number_of_nodes()):
        new_graph.nodes[i]['team'] = assignment[i]

    return new_graph

def update_leaderboard(leaderboard, new_item, max_length):
    """
    Updates the leaderboard with the new item (if it qualifies)
    """
    if len(leaderboard) < max_length or leaderboard[-1]['score'] > new_item['score']:
        leaderboard.append(new_item)
        leaderboard.sort(key=lambda x:x['score'], reverse=False)
        if len(leaderboard) > max_length:
            leaderboard = leaderboard[:-1]
    return leaderboard

def solve(input: nx.Graph) -> nx.Graph:
    """
    Returns the solved version of the graph
    """
    # Assign a team to v with G.nodes[v]['team'] = team_id
    # Access the team of v with team_id = G.nodes[v]['team']
    
    # iterate over team #
    NUM_ORIGINAL_SAMPLES = 3 # number of initial samples per team_size
    CUTOFF = 1000 # when to stop increasing num_teams
    NUM_GRAPHS_TO_RESAMPLE = 10
    NUM_RESAMPLES = 10
    NUM_GRAPHS_TO_IMPROVE = 10
    NUM_IMPROVEMENTS = 5

    current_best_score = math.inf
    
    graphs_to_resample = []
    
    for num_teams in range(1, input.number_of_edges()//2):

        samples = []
        # take n different samples at each team size
        for i in range(NUM_ORIGINAL_SAMPLES):

            candidate = random_graph(input, num_teams)

            current_score = score(candidate)
            if current_score < current_best_score:
                current_best_score = current_score

            new_item = {'graph': candidate.copy(), 'num_teams': num_teams, 'score':current_score}
            graphs_to_resample = update_leaderboard(graphs_to_resample, new_item, NUM_GRAPHS_TO_RESAMPLE)
            samples.append(current_score)

        # Finishes incrementing num_teams if performance gets bad enough
        if round(min(samples)) > current_best_score * CUTOFF:
            break
    
    graphs_to_improve = []
    for item in graphs_to_resample:

        # Appends the original item to the list if it is good enough
        graphs_to_improve = update_leaderboard(graphs_to_improve, item, NUM_GRAPHS_TO_IMPROVE)

        for i in range(NUM_RESAMPLES):
            candidate = random_graph(input, item['num_teams'])
            new_item = {'graph': candidate.copy(), 'num_teams': item['num_teams'], 'score':score(candidate)}
            graphs_to_improve = update_leaderboard(graphs_to_improve, new_item, NUM_GRAPHS_TO_IMPROVE)

    current_best = None
    current_best_score = math.inf

    for item in graphs_to_improve:
        candidate_best_score = item['score']
        candidate = item['graph'].copy()
        for i in range(NUM_IMPROVEMENTS):
            improved_graph = improve_worst_team(candidate)
            improved_graph_score = score(improved_graph)
            if improved_graph_score < candidate_best_score:
                candidate = improved_graph.copy()
                candidate_best_score = improved_graph_score
        if candidate_best_score < current_best_score:
            current_best = candidate.copy()

    return current_best


input = read_input('./inputs/large.in')
final = solve(input)
validate_output(final)
print('Final score:', score(final))

# Use once algorithm is complete
# run_all(solve, './inputs', './outputs01', overwrite=True)