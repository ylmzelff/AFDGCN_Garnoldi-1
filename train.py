import os
import torch
import numpy as np
import torch.nn as nn
from config import args
from datetime import datetime
import torch.nn.functional as F
from model.AFDGCN import Model as Network
from engine import Engine
from lib.metrics import MAE_torch
from lib.TrainInits import init_seed
from lib.dataloader import get_dataloader
from lib.TrainInits import print_model_parameters
from lib.load_graph import get_Gaussian_matrix, get_adjacency_matrix
import scipy.sparse as sp
# *****************************************  参数初始化配置      Parametre başlatma yapılandırması ****************************************** #
init_seed(args.seed)

if torch.cuda.is_available() and torch.cuda.device_count() > 0:
    device = torch.device('cuda:0')  # Use the first GPU
    print(f"Using GPU    : {torch.cuda.get_device_name(0)}")
else:
    device = torch.device('cpu')
    print("CUDA is not available. Falling back to CPU.")

#A = get_Gaussian_matrix(args.graph_path, args.num_nodes, args.normalized_k, id_filename=args.filename_id)

def myminimum(A,B):
    BisBigger = A-B
    BisBigger.data = np.where(BisBigger.data >= 0, 1, 0)
    return A - A.multiply(BisBigger) + B.multiply(BisBigger)

def normalize_adjHPI(adj):
    adj = sp.coo_matrix(adj)

    rowsum = np.array(adj.sum(1))
    
    deg_row = np.tile(rowsum, (1,adj.shape[0]))
    
    #deg_row = deg_row.T
    deg_row = sp.coo_matrix(deg_row)
    
    sim = adj.dot(adj)
    
    #y = sim.copy().tocsr()
    #y.data.fill(1)
    X = sim.astype(bool).astype(int)
    deg_row = deg_row.multiply(X)
    
    deg_row = myminimum(deg_row, deg_row.T)
    
    sim = sim/deg_row
    #sim = sp.coo_matrix(sim)
    whereAreNan = np.isnan(sim)
    whereAreInf = np.isinf(sim)
    sim[whereAreNan] = 0
    sim[whereAreInf] = 0
    
    sim = sp.coo_matrix(sim)
    #print(sim[0])
    return sim.toarray()

def normalize_adjAA(W):
    # Calculate row sums
    rowsum = np.array(W.sum(1))
    # Check for zero values in rowsum
    zero_indices = np.where(rowsum == 0)
    # Handle zero values by setting them to a small positive number (e.g., 1e-6)
    rowsum[zero_indices] = 1e-6
    # Calculate the inverse root of rowsum
    d_inv_sqrt = np.power(np.log(rowsum), -1).flatten()
    # Handle infinity values by setting them to 0
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.0
    # Create a diagonal matrix from d_inv_sqrt
    d_mat_inv_sqrt = np.diag(d_inv_sqrt)
    # Calculate the normalized adjacency matrix
    DA = d_mat_inv_sqrt.dot(W)
    
    return W.dot(DA)


def normalize_adjCN(W):
   # ctx = mx.gpu()
    rowsum = np.array(W.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
   # d_mat_inv_sqrt = mx.nd.array(np.diag(d_inv_sqrt), ctx=ctx)
    return np.dot(W, W)


def normalize_adjHDI(adj):
    adj = sp.coo_matrix(adj)
    rowsum = np.array(adj.sum(1))
    deg_row = np.tile(rowsum, (1, adj.shape[0]))
    deg_row = sp.coo_matrix(deg_row)

    sim = adj.dot(adj)

    X = sim.astype(bool).astype(int)
    deg_row = deg_row.multiply(X)

    # Handle division by zero by checking for zero entries in deg_row
    nonzero_indices = deg_row.data.nonzero()  # Get indices where data is non-zero
    deg_row.data[nonzero_indices] = 1.0 / deg_row.data[nonzero_indices]
    deg_row.data[~np.isfinite(deg_row.data)] = 0  # Set inf and NaN values to zero

    sim = sim.multiply(deg_row)

    sim = mymaximum(sim, sim.T)  # Ensure mymaximum is defined

    sim = np.array(sim.toarray())  # Convert the result to a NumPy array

    return sim

def normalize_adj(adj):
    adj = sp.coo_matrix(adj)
    rowsum = np.array(adj.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
    sim = adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt).tocoo()
    
    sim = np.array(sim.toarray())  # Convert the result to a NumPy array

    return sim

def mymaximum (A, B):
    BisBigger = A-B
    BisBigger.data = np.where(BisBigger.data <= 0, 1, 0)
    return A - A.multiply(BisBigger) + B.multiply(BisBigger)

def perturb_adjacency_matrix(adj_matrix, perturbation_factor=0.1):
    """
    Perturb the adjacency matrix by adding a random perturbation.
    
    Parameters:
    - adj_matrix: Original adjacency matrix
    - perturbation_factor: Factor to control the amount of perturbation
    
    Returns:
    - Perturbed adjacency matrix
    """
    np.random.seed(42)  # Set a seed for reproducibility
    perturbation = np.random.uniform(low=-perturbation_factor, high=perturbation_factor, size=adj_matrix.shape)
    perturbed_adj_matrix = adj_matrix + perturbation
    
    # Ensure the resulting matrix is symmetric
    perturbed_adj_matrix = 0.5 * (perturbed_adj_matrix + perturbed_adj_matrix.T)
    
    return perturbed_adj_matrix

# load dataset
Adj = get_adjacency_matrix(args.graph_path, args.num_nodes, type='connectivity', id_filename=args.filename_id)
#A = torch.FloatTensor(A).to(args.device)

#adj_tensor = torch.tensor(Adj, dtype=torch.float32)
#A = F.softmax(F.relu(torch.mm(adj_tensor, adj_tensor.t())), dim=1)
#A=F.softmax(F.relu(adj_tensor.t()), dim=1)
Adj=normalize_adj(Adj)
A=torch.tensor(Adj, dtype=torch.float32)
#A=torch.tensor(Adj, dtype=torch.float32).to(torch.device('cuda:0'))

train_loader, val_loader, test_loader, scaler = get_dataloader(args,
                                                               normalizer=args.normalizer,
                                                               tod=args.tod, 
                                                               dow=False,
                                                               weather=False, 
                                                               single=False)
print("train loader ",len(train_loader))
# *****************************************  初始化模型参数 ****************************************** #
input_dim = 1
hidden_dim = 64 
output_dim = 1
embed_dim = 15 #19#8   if you used adj, number of nodes should be entered here
cheb_k = 2
horizon = 1
num_layers = 1 
heads = 4
timesteps = 1
kernel_size = 5
model = Network(num_node = args.num_nodes, 
                input_dim = input_dim, 
                hidden_dim = hidden_dim, 
                output_dim = output_dim, 
                embed_dim = embed_dim, 
                cheb_k = cheb_k, 
                horizon = horizon, 
                num_layers = num_layers, 
                heads = heads, 
                timesteps = timesteps, 
                A = A,
                kernel_size=kernel_size)
model = model.to(args.device)
# os.environ['CUDA_VISIBLE_DEVICES'] = '0, 1, 2, 3, 4'
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# if torch.cuda.device_count() > 1:
#     model = nn.DataParallel(model.cuda(), device_ids=[3, 4])
for p in model.parameters():
    if p.dim() > 1:
        nn.init.xavier_uniform_(p)
    else:
        nn.init.uniform_(p)
# print the number of model parameters
print_model_parameters(model, only_num=False)
# *****************************************  定义损失函数、优化器 ****************************************** #
# 1. init loss function, optimizer
def masked_mae_loss(scaler, mask_value):
    def loss(preds, labels):
        if scaler:
            preds = scaler.inverse_transform(preds)
            labels = scaler.inverse_transform(labels)
        mae = MAE_torch(pred=preds, true=labels, mask_value=mask_value)
        return mae
    return loss
if args.loss_func == 'mask_mae':
    loss = masked_mae_loss(scaler, mask_value=0.0)
elif args.loss_func == 'mae':
    loss = torch.nn.L1Loss().to(args.device)
elif args.loss_func == 'mse':
    loss = torch.nn.MSELoss().to(args.device)
elif args.loss_func == 'smoothloss':
    loss = torch.nn.SmoothL1Loss().to(args.device)
else:
    raise ValueError
# 2. init optimizer
optimizer = torch.optim.Adam(params=model.parameters(), lr=args.lr_init, eps=1.0e-8,
                             weight_decay=0, amsgrad=False)
# 3. learning rate decay
lr_scheduler = None
if args.lr_decay:
    print('Applying learning rate decay.')
    lr_decay_steps = [int(i) for i in list(args.lr_decay_step.split(','))]
    lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer=optimizer,
                                                        milestones=lr_decay_steps,
                                                        gamma=args.lr_decay_rate)
# *****************************************  模型训练与测试 ****************************************** #
# 1.config log path
current_time = datetime.now().strftime('%Y%m%d%H%M%S')
current_dir = os.path.dirname(os.path.realpath(__file__))
log_dir = os.path.join(current_dir,'experiments', args.dataset, current_time)
os.makedirs(log_dir, exist_ok=True)
print(log_dir)
args.log_dir = log_dir

# 2.start training
trainer = Engine(model, 
                  loss, 
                  optimizer, 
                  train_loader, 
                  val_loader, 
                  test_loader, 
                  scaler,
                  args, 
                  lr_scheduler)
if args.mode == 'train':
    trainer.train()
elif args.mode == 'test':
    checkpoint = "D:\AFDGCN\experiments\PEMS04\garnoldi_pems_best" # en yeni modeli kullan
    model.load_state_dict(torch.load(checkpoint, map_location=torch.device('cpu')))

   # model.load_state_dict(torch.load(checkpoint))  # map_location='cuda:5'
    # node_embedding = model.node_embedding
    # adj = F.softmax(F.relu(torch.mm(node_embedding, node_embedding.transpose(0, 1))), dim=1) adj transpose
    # adj = torch.mm(node_embedding, node_embedding.transpose(0, 1))
    # print(adj.shape)
    # np.save('adaptive_matrix.npy', adj.detach().cpu().numpy())
    
    model.load_state_dict(torch.load(checkpoint))  # map_location='cuda:5'
    adj_tensor = torch.tensor(Adj, dtype=torch.float32)
    adj_tensor = adj_tensor.to(torch.device('cuda')) 
    adj = F.softmax(F.relu(torch.mm(adj_tensor, adj_tensor.t())), dim=1)
    print(adj.shape)
    np.save('adaptive_matrix.npy', adj.detach().cpu().numpy())
    print("load saved model...")
    trainer.test(model, trainer.args, test_loader, scaler, trainer.logger)
else:
    raise ValueError
