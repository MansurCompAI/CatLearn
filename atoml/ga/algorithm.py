"""The GeneticAlgorithm class methods."""
import numpy as np
import random
import warnings

from .initialize import initialize_population
from .mating import cut_and_splice
from .mutate import random_permutation
from .convergence import Convergence


class GeneticAlgorithm(object):
    """Genetic algorithm for parameter optimization."""

    def __init__(self, population_size, fit_func, dimension, population=None,
                 operators=None):
        """Initialize the genetic algorithm.

        Parameters
        ----------
        population_size : int
            Population size, same as generation size.
        fit_func : object
            User defined function to calculate fitness.
        d_param : int
            Dimension of parameters in model.
        population : list
            The current population. Default is None.
        operators : list
            A list of operation functions. These are used for mating and
            mutation operations.
        """
        # Set parameters.
        self.population_size = population_size
        self.fit_func = fit_func
        self.dimension = dimension

        # Define the starting population.
        self.population = population
        if self.population is None:
            self.population = initialize_population(population_size, dimension)

        # Define the operators to use.
        self.operators = operators
        if self.operators is None:
            self.operators = [cut_and_splice, random_permutation]

    def search(self, steps, verbose=False, repeat=5):
        """Do the actual search.

        Parameters
        ----------
        steps : int
            Maximum number of steps to be taken.
        verbose : bool
            If True, will print out the progress of the search. Default is
            False.
        repeat : int
            Number of repeat generations with no progress.

        Attributes
        ----------
        population : list
            The current population.
        fitness : list
            The fitness for the current population.
        """
        self.fitness = self._get_fitness(self.population)
        if verbose:
            self._print_data()

        # Initialixe the convergence check.
        converge_check = Convergence()
        converge_check.no_progress(self.fitness, repeat=repeat)

        for step in range(steps):
            offspring_list = self._new_generation()

            # Keep track of fitness for new candidates.
            new_fit = self._get_fitness(offspring_list)
            if new_fit is None:
                break

            # Combine data sets.
            extend_fit = np.concatenate((self.fitness, new_fit))
            extend_pop = np.concatenate((self.population, offspring_list))

            # Perform natural selection.
            self._population_reduction(extend_pop, extend_fit)

            if verbose:
                self._print_data()

            if converge_check.no_progress(self.fitness, repeat=repeat):
                print('CONVERGED on step {}'.format(step + 1))
                break

    def _new_generation(self):
        """Create a new generation of candidates.

        Returns
        -------
        offspring_list : list
            A list of paramteres for the new generation.
        """
        offspring_list = []
        for c in range(self.population_size):
            # Select an initial candidate.
            p1 = None
            while p1 is None:
                p1 = self._selection(self.population, self.fitness)

            # Select a random operator.
            operator = random.choice(self.operators)

            # First check for mating.
            if operator is cut_and_splice:
                p2 = p1
                while p2 is p1 or p2 is None:
                    p2 = self._selection(self.population, self.fitness)
                offspring_list.append(operator(p1, p2))

            # Otherwise perfrom mutation.
            else:
                offspring_list.append(operator(p1))

        return offspring_list

    def _selection(self, param_list, fit_list):
        """Perform natural selection.

        Parameters
        ----------
        param_list : list
            List of parameter sets to consider.
        fit_list : list
            list of fitnesses associated with parameter list.

        Returns
        -------
        parameter : array
            A selected set of parameters from the population.
        """
        length = len(fit_list)
        index = list(range(length))
        index_shuf = list(range(length))
        random.shuffle(index_shuf)

        # Combine data and sort.
        fit = list(zip(*sorted(zip(fit_list, index), reverse=True)))

        # Define some probability scaling.
        scale, s = [], 0
        for _ in range(length):
            s += 1 / (length + 2)
            scale.append(s)

        fit_list = list(zip(*sorted(zip(fit[1], scale), reverse=False)))[1]

        # Reorder the fitness and parameter lists.
        param_list_shuf, fit_list_shuf = [], []
        for ind in index_shuf:
            param_list_shuf.append(param_list[ind])
            fit_list_shuf.append(fit_list[ind])

        # Get random probability.
        for parameter, fitness in zip(param_list_shuf, fit_list_shuf):
            if fitness > np.random.rand(1)[0]:
                return parameter

        return None

    def _population_reduction(self, pop, fit):
        """Method to reduce population size to constant.

        Parameters
        ----------
        pop : list
            Extended population.
        fit : list
            Extended fitness assignment.

        Attributes
        ----------
        pop : list
            The population after natural selection.
        fitness : list
            The fitness for the current population.
        """
        # Combine parameters and sort.
        global_details = [[i, j] for i, j in zip(pop, fit)]
        global_details.sort(key=lambda x: float(x[1]), reverse=True)

        # Reinitialize everything as empty list.
        self.population, self.fitness, unique_list = [], [], []

        # Fill the lists with current best candidates.
        for i in global_details:
            if len(self.population) < self.population_size:
                # Round to some tolerance to make sure unique fitness.
                if round(i[1], 5) not in unique_list:
                    self.population.append(i[0])
                    self.fitness.append(i[1])
                    unique_list.append(round(i[1], 5))
            else:
                break

    def _get_fitness(self, param_list):
        """Function wrapper to calculate the fitness.

        Parameters
        ----------
        param_list : list
            List of new parameter sets to get fitness for.

        Returns
        -------
        fit : array
            The fitness based on the new parameters.
        """
        # Initialize array.
        fit = np.zeros(len(param_list))

        bool_list = np.asarray(param_list, dtype=np.bool)
        for index, parameter in enumerate(bool_list):
            try:
                calc_fit = self.fit_func(parameter)
            except ValueError:
                # If there is a problem calculating fitness assign -inf.
                calc_fit = float('-inf')
                msg = 'The fitness function is failing. Returning -inf.'
                warnings.warn(msg)

            fit[index] = calc_fit

        return fit

    def _print_data(self):
        """Print some output during the search."""
        msg = 'new generation, current best fitness: {0:.3f} '.format(
            np.max(self.fitness))
        msg += 'mean fitness: {0:.3f}, worst fitness: {1:.3f}'.format(
            np.mean(self.fitness), np.min(self.fitness))

        print(msg)