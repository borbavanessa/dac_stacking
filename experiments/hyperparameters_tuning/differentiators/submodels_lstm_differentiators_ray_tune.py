import argparse
import sys
from keras.utils.vis_utils import plot_model

parser = argparse.ArgumentParser()
parser.add_argument("--smoke-test", action="store_true", help="Finish quickly for testing")
args, _ = parser.parse_known_args()


def generate_model(set_params, train_mode=True):
		from utils.experiment_processes import ExperimentProcesses
		import utils.definition_network as dn
		
		exp = ExperimentProcesses(set_params['function'])
		exp.pp_data.vocabulary_size = 5000
		
		exp.pp_data.embedding_size = 300
		exp.pp_data.max_posts = 1750
		exp.pp_data.max_terms_by_post = 300
		exp.pp_data.binary_classifier = True
		exp.pp_data.format_input_data = dn.InputData.POSTS_ONLY_TEXT
		exp.pp_data.remove_stopwords = False
		exp.pp_data.delete_low_tfid = False
		exp.pp_data.min_df = 0
		exp.pp_data.min_tf = 0
		exp.pp_data.random_posts = False
		exp.pp_data.random_users = True
		exp.pp_data.tokenizing_type = 'WE'
		exp.pp_data.type_prediction_label = dn.TypePredictionLabel.MULTI_LABEL_CATEGORICAL
		
		exp.use_custom_metrics = False
		exp.use_valid_set_for_train = True
		exp.valid_split_from_train_set = 0.0
		exp.imbalanced_classes = False
		
		exp.pp_data.embedding_type = set_params['embedding_type']
		exp.pp_data.word_embedding_custom_file = set_params['custom_file']
		exp.pp_data.use_embedding = set_params['use_embedding']
		
		if train_mode:
				exp.pp_data.load_dataset_type = dn.LoadDataset.TRAIN_DATA_MODEL
		else:
				exp.pp_data.load_dataset_type = dn.LoadDataset.TEST_DATA_MODEL

		exp.pp_data.set_dataset_source(dataset_name='SMHD', label_set=['control', 'anxiety', 'depression'],
																	 total_registers=set_params['total_registers'], subdirectory=set_params['subdirectory'])

		return exp


# https://github.com/tensorflow/tensorflow/issues/32159
def train_submodel_diff(config):
		from keras.models import Sequential
		from keras.layers import Dense
		from keras.layers import LSTM
		from keras.layers import Embedding
		from keras.callbacks import ModelCheckpoint
		from keras.optimizers import Adam
		from ray.tune.integration.keras import TuneReporterCallback
		import utils.definition_network as dn
		import pandas as pd
		from ray import tune
		
		x_train, y_train, x_valid, y_valid, num_words, embedding_matrix = config["exp_sets"].pp_data.load_data()
		
		trainable_emb = (config["exp_sets"].pp_data.use_embedding == (dn.UseEmbedding.RAND or dn.UseEmbedding.NON_STATIC))
		
		layers_model = [Embedding(config["exp_sets"].pp_data.vocabulary_size, config["exp_sets"].pp_data.embedding_size,
																	trainable=trainable_emb, name=config["name"]+'_rt_emb_1')]
												
		for id_hl in range(config["hidden_layers"]-1):
				layers_model.append(LSTM(config["lstm_units"], kernel_initializer='lecun_uniform',
														 activation='tanh', dropout=config["dropout_lstm"],
														 recurrent_dropout=config["dropout_lstm"],
														 return_sequences=True, name=config["name"]+'_rt_lstm_'+str(id_hl)))
				
		layers_model.append(LSTM(config["lstm_units"], kernel_initializer='lecun_uniform',
														 activation='tanh', dropout=config["dropout_lstm"],
														 recurrent_dropout=config["dropout_lstm"],
														 name=config["name"]+'_rt_lstm_'+str(id_hl+1)))
		
		layers_model.append(Dense(3, activation='sigmoid', name=config["name"]+'_rt_dense_1'))
		
		model = Sequential(layers_model)
		model.compile(loss="binary_crossentropy",
									optimizer=Adam(lr=config["lr"]),
									metrics=["accuracy"])
		
		history = model.fit(x_train,
												y_train,
												batch_size=config["batch_size"],
												epochs=config["epochs"],
												verbose=0,
												validation_data=(x_valid, y_valid),
												callbacks=[TuneReporterCallback(freq="epoch"),
																	 ModelCheckpoint(tune.get_trial_dir() + 'train_model.h5',
																									 monitor='val_acc', mode='max', save_best_only=True,
																									 save_weights_only=False, verbose=0)])


		hist_df = pd.DataFrame(history.history)
		with open(tune.get_trial_dir() + 'history_train_model.csv', mode='w') as file:
				hist_df.to_csv(file)


def config_word_emb_glove_6b(config_test_dct):
		from ray import tune
		import numpy as np
		import random
		import utils.definition_network as dn
		
		return {
				"name": "g6_lstm_t1",
				"exp_sets": generate_model(
						dict({
								'function': 'glove6b',
								'embedding_type': dn.EmbeddingType.GLOVE_6B,
								'custom_file': '',
								'use_embedding': dn.UseEmbedding.STATIC,
								'total_registers': config_test_dct['total_registers'],
								'subdirectory': config_test_dct['subdirectory']
						})
				),
				"batch_size": tune.sample_from(lambda spec: random.choice([20, 10, 25, 40])),
				"epochs": tune.sample_from(lambda spec: np.random.randint(32, 80)),
				"threads": 2,
				"lr": tune.sample_from(lambda spec: np.random.uniform(0.001, 0.01)),
				# "momentum": tune.sample_from(lambda spec: np.random.uniform(0.1, 0.9)),
				"lstm_units": tune.sample_from(lambda spec: np.random.randint(16, 128)),
				"dropout_lstm": tune.sample_from(lambda spec: np.random.uniform(0.2, 0.4)),
				"hidden_layers": tune.sample_from(lambda spec: np.random.randint(3, 5))
		}


def config_word_emb_glove_custom(config_test_dct):
		from ray import tune
		import numpy as np
		import random
		import utils.definition_network as dn
		
		return {
				"name": "gc_lstm_t1",
				"exp_sets": generate_model(
						dict({
								'function': 'glove_custom',
								'embedding_type': dn.EmbeddingType.GLOVE_CUSTOM,
								'custom_file': 'SMHD-glove-A-D-ADUsers-300.pkl',
								'use_embedding': dn.UseEmbedding.STATIC,
								'total_registers': config_test_dct['total_registers'],
								'subdirectory': config_test_dct['subdirectory']
						})
				),
				"batch_size": tune.sample_from(lambda spec: random.choice([20, 10, 25, 40])),
				"epochs": tune.sample_from(lambda spec: np.random.randint(32, 80)),
				"threads": 2,
				"lr": tune.sample_from(lambda spec: np.random.uniform(0.001, 0.01)),
				# "momentum": tune.sample_from(lambda spec: np.random.uniform(0.1, 0.9)),
				"lstm_units": tune.sample_from(lambda spec: np.random.randint(16, 128)),
				"dropout_lstm": tune.sample_from(lambda spec: np.random.uniform(0.2, 0.4)),
				"hidden_layers": tune.sample_from(lambda spec: np.random.randint(3, 5))
		}


def config_word_emb_w2v_custom(config_test_dct):
		from ray import tune
		import numpy as np
		import random
		import utils.definition_network as dn
		
		return {
				"name": "wc_lstm_t1",
				"exp_sets": generate_model(
						dict({
								'function': 'w2vCustom',
								'embedding_type': dn.EmbeddingType.WORD2VEC_CUSTOM,
								'custom_file': 'SMHD-CBOW-A-D-ADUsers-300.bin',
								'use_embedding': dn.UseEmbedding.NON_STATIC,
								'total_registers': config_test_dct['total_registers'],
								'subdirectory': config_test_dct['subdirectory']
						})
				),
				"batch_size": tune.sample_from(lambda spec: random.choice([20, 10, 25, 40])),
				"epochs": tune.sample_from(lambda spec: np.random.randint(32, 80)),
				"threads": 2,
				"lr": tune.sample_from(lambda spec: np.random.uniform(0.001, 0.01)),
				# "momentum": tune.sample_from(lambda spec: np.random.uniform(0.1, 0.9)),
				"lstm_units": tune.sample_from(lambda spec: np.random.randint(16, 128)),
				"dropout_lstm": tune.sample_from(lambda spec: np.random.uniform(0.2, 0.4)),
				"hidden_layers": tune.sample_from(lambda spec: np.random.randint(3, 5))
		}


def ray_tune_train(config_test_dct):
		import ray
		from ray import tune
		from ray.tune.schedulers import AsyncHyperBandScheduler
		
		if config_test_dct['option'] == '1':
				config_test = config_word_emb_glove_6b(config_test_dct)
		elif config_test_dct['option'] == '2':
				config_test = config_word_emb_glove_custom(config_test_dct)
		else:
				config_test = config_word_emb_w2v_custom(config_test_dct)


		ray.init(num_cpus=6 if args.smoke_test else None)
		sched = AsyncHyperBandScheduler(time_attr="training_iteration",
																		metric="mean_accuracy",
																		mode="max",
																		max_t=200,
																		grace_period=20)
		tune.run(
				train_submodel_diff,
				name="exp_lstm_"+config_test_dct['option'],
				scheduler=sched,
				stop={"mean_accuracy": 0.90,
							"training_iteration": 20 if args.smoke_test else 100},  # 10 if args.smoke_test else 300
				num_samples=10,
				resources_per_trial={
						"cpu": 2,
						"gpu": 0
				},
				config=config_test
		)


def run_predicions_model(file_path, exp):
		from network_model.model_class import ModelClass
		from keras.models import load_model
		
		name_test = file_path.split('/')
		exp.experiment_name = name_test[len(name_test) - 1]
		
		x_test, y_test = exp.pp_data.load_data()
		
		model_class = ModelClass(1)
		
		model_class.model = load_model(file_path + '.h5', custom_objects=None, compile=True)
		exp.save_geral_configs('Experiment Specific Configuration: ' + exp.experiment_name)
		exp.save_summary_model(model_class.model)
		exp.predict_samples(model_class, x_test, y_test)
		plot_model(model_class.model, to_file=file_path + '/train_model.png', show_shapes=True, show_layer_names=True)


def test_best_model_ray_tune(set_params):
		exp = generate_model(set_params, train_mode=False)
		run_predicions_model(set_params['path_model'], exp)
		del exp

# Execute python3.6 submodels_lstm_differentiators_ray_tune.py 1 A_AD
if __name__ == "__main__":
		# Tunning hyperparams model
		option = sys.argv[1]
		function = sys.argv[2]

		if function == 'A_D':
				ray_tune_train({'total_registers': 1040, 'subdirectory': 'only_disorders/A_D', 'option': option})

		else:  # A_AD, D_AD
				ray_tune_train({'total_registers': 880, 'subdirectory': 'only_disorders/' + function, 'option': option})

