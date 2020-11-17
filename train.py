import argparse, math, os, sys
from copy import deepcopy
import numpy as np
import robosuite as suite
import wandb

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from models.REINFORCE import REINFORCE
from models.DDPG import DDPG



def train_reinforce():
    agent = REINFORCE(state_dim,env.action_dim, args.gamma, args.lr, args.num_episodes, args.horizon, args.hidden_size)

    for epoch in range(args.num_epochs):
        log_probs = [[] for i in range(args.num_episodes)]
        rewards = [[] for i in range(args.num_episodes)]
        for episode in range(args.num_episodes):
            obs=env.reset()
            done=False
            while done==False:
                state = torch.Tensor(np.append(obs['robot0_robot-state'],obs['object-state'])) 
                action, log_prob = agent.select_action(state)
                action_cpu = [x.to('cpu') for x in action]
                obs, reward, done, info = env.step(action_cpu)
                log_probs[episode].append(log_prob)
                rewards[episode].append(reward)
                
        agent.epoch_update_parameters(rewards, log_probs)
        print('Epoch: {}, Average_Rewards: {}'.format(epoch, np.sum(rewards,axis=1).mean()))
        wandb.log({'epoch_reward': np.sum(rewards,axis=1).mean()})

        if epoch%20==0:
            torch.save(agent.model.state_dict(),'{}.pkl'.format(args.wandb_name))
            wandb.save('{}.pkl'.format(args.wandb_name))


def train_ddpg():
    agent = DDPG(state_dim, env.action_dim, args)
    iteration = 0
    for epoch in range(args.num_epochs):
        rewards = []
        for episode in range(args.num_episodes):
            obs = env.reset()
            state = np.append(obs['robot0_robot-state'],obs['object-state'])
            agent.s_t = state
            done=False
            while done==False: 
                if iteration <= args.warmup:
                    action = agent.random_action()
                    iteration += 1
                else:
                    action = agent.select_action(state)           
                    iteration += 1
                obs, reward,done, info = env.step(action)
                rewards.append(reward)
                state = np.append(obs['robot0_robot-state'],obs['object-state'])
                agent.observe(reward, state, done)
                if iteration > args.warmup:
                    agent.update_parameters()

        print('Epoch: {}, Average_Rewards: {}'.format(epoch, np.sum(rewards)/len(rewards)))
        wandb.log({'epoch_reward': np.sum(rewards)/len(rewards)})

        if epoch%20==0:
            torch.save(agent.actor,'{}.pt'.format(args.wandb_name))
            wandb.save('{}.pt'.format(args.wandb_name))




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PyTorch robot arm training script')
    parser.add_argument('--env_name', type=str, default='Lift')
    parser.add_argument('--robot', type=str, default='Panda')
    parser.add_argument('--algo', type=str, default='DDPG')
    parser.add_argument('--hidden_size', type=int, default=256)
    parser.add_argument('--max_mem_size', type=int, default=50000)
    parser.add_argument('--tau', type=float, default=0.001)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--lr_actor', type=float, default=0.0001)
    parser.add_argument('--lr_critic', type=float, default=0.001)
    parser.add_argument('--epsilon', type=float, default=10000)
    parser.add_argument('--warmup', type=int, default=100)
    parser.add_argument('--theta', type=int, default=0.15)
    parser.add_argument('--gamma', type=float, default=0.99,
                        help='discount factor for reward (default: 0.99)')
    parser.add_argument('--num_epochs',type=int, default=500,
                        help='number of epochs to train on' )
    parser.add_argument('--num_episodes', type=int, default=500,
                        help='number of episodes per epoch')
    parser.add_argument('--horizon', type=int, default=200,
                        help='max episode length (default: 200)')
    parser.add_argument('--wandb_api', type=str, default=None, 
                        help='wandb api key')
    parser.add_argument('--wandb_project', type=str, default='cs221-project',
                        help='wandb project name')
    parser.add_argument('--wandb_name', type=str, default='test-run',
                        help='name of run')
    parser.add_argument('--wandb_entity', type=str, default='peterdavidfagan', metavar='N',
                        help='name of user running experiment')
    args = parser.parse_args()

    os.environ['WANDB_API_KEY'] = args.wandb_api
    os.environ['WANDB_PROJECT'] = args.wandb_project
    os.environ['WANDB_NAME'] =  args.wandb_name
    os.environ['ENTITY'] = args.wandb_entity

    wandb.init()
    wandb.config.gamma = args.gamma
    wandb.config.horizon = args.horizon
    wandb.config.num_episodes = args.num_episodes

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Setting up the robot enviornment
    env = suite.make(
        env_name=args.env_name,
        robots=args.robot,
        has_renderer=False,
        has_offscreen_renderer=False,
        use_camera_obs=False,
        use_object_obs=True,                    
        horizon = args.horizon, 
        reward_shaping=True                 
    )
    obs = env.reset()
    state_dim = obs['robot0_robot-state'].shape[0]+obs['object-state'].shape[0]

    # Setting algorithm according to args
    if args.algo == 'REINFORCE':
        print('Starting to train REINFORCE...')
        train_reinforce()
    elif args.algo == 'DDPG':
        print('Starting to train DDPG')
        train_ddpg()        
    else:
        sys.exit('Incorrect algorithms specification. Please check the algorithm argument provided.')

