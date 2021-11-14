import numpy as np
# import matplotlib.pyplot as plt
import tensorflow as tf
import copy
from utils import data_splitter, normalize
from computations import get_logits,get_accuracy,svgd_update

num_classes = 10
num_epochs = 100
latent_dim = 64
num_samples = 10
batch_size = 32
norm_flag = True #Whether to normalize embeddings and weights for computing logits
alpha = 1.0 #Scaling factor
reg = 1e-3

def train_step(X,y,weights_list,optimizer,num_lab):
    with tf.GradientTape(persistent=True) as tape:
        cce = tf.losses.CategoricalCrossentropy(from_logits=True)
        # Forward pass
        losses_list = []
        reg_list = []
        for weights in weights_list:
            logits = get_logits(X,weights,norm_flag)
            losses_list.append(cce(y, alpha*logits))
            reg_list.append(reg*tf.reduce_sum(tf.square(weights)))
        #Compute Loss
    #Get gradients
    params_list = [[weights] for weights in weights_list]
    losses_grads_list = [tape.gradient(loss,weights) for (loss,weights) in zip(losses_list,weights_list)]
    reg_grads_list = [tape.gradient(reg,weights) for (reg,weights) in zip(reg_list,weights_list)]
    sf = float(num_lab/batch_size)
    grads_list = [[reg_grad + sf*loss_grad] for (loss_grad,reg_grad) in zip(losses_grads_list,reg_grads_list)] #Total gradient
    if num_samples>1:
    #Update gradients
        grads_list = svgd_update(grads_list,params_list,num_samples)
    # Apply gradients
    for (grads,params) in zip(grads_list,params_list):
        optimizer.apply_gradients(zip(grads,params))
    return weights_list,optimizer

def val_step(X_val,y_val,weights_list):
    probs_list = []
    for weights in weights_list:
        logits = get_logits(X_val,weights,norm_flag)
        probs = tf.nn.softmax(alpha*logits)
        probs_list.append(probs)
    val_probs = tf.reduce_mean(tf.stack(probs_list),axis=0)
    val_acc_check = get_accuracy(val_probs,y_val).numpy()
    return val_acc_check

def train(X,y,X_val,y_val):
    #Trains the model on data X and labels y
    num_lab = X.shape[0]
    val_acc = 0.0
    dataset = tf.data.Dataset.from_tensor_slices((X,y))
    dataset = dataset.shuffle(1000).batch(batch_size)
    optimizer = tf.keras.optimizers.Nadam(learning_rate = 1e-3, name='Nadam')
    weights_list = [tf.Variable(tf.random.normal((num_classes,X.shape[1]))) for _ in range(num_samples)]
    for epoch in range(num_epochs):
        #Training
        for (batch, (points, targets)) in enumerate(dataset):
            weights_list, optimizer = train_step(points,targets,weights_list,optimizer,num_lab)
        #Validation
        if epoch%10 == 0 or epoch == num_epochs-1:
            val_acc_check = val_step(X_val,y_val,weights_list)
            # print ([epoch, val_acc_check])
            if val_acc_check >= val_acc:
                val_acc = val_acc_check
                best_weights_list = [weights.numpy() for weights in weights_list]
            else:
                continue #Don't save if performance worsens
    return best_weights_list

mnist = tf.keras.datasets.mnist
(X_train, y_train), (X_test, y_test) = mnist.load_data()
y_train = tf.one_hot(y_train,depth=num_classes,axis=-1).numpy()
y_test = tf.one_hot(y_test,depth=num_classes,axis=-1).numpy()
X_train = X_train.reshape((X_train.shape[0],-1))/255.0
X_train = X_train.astype('float32')
X_test = X_test.reshape((X_test.shape[0],-1))/255.0
X_test = X_test.astype('float32')

num_trials = 10
num_lab_max = 1000
num_acq = 100
acc = np.zeros((10,num_trials))
negll = np.zeros((10,num_trials))

for trial in range(num_trials):
    print ('Trial = '+str(trial))
    num_lab = 100
    ctr = 0
    while num_lab<=num_lab_max:
        num_val = int(0.1*num_lab)
        X_lab, y_lab, X_unlab, y_unlab = data_splitter(X_train, y_train, num_lab) #Splitting into labeled and unlabeled data
        X_val, y_val, X, y = data_splitter(X_lab,y_lab, num_val)
        weights_list = train(X,y,X_val,y_val)  
        #Checking accuracy on test data
        probs_list = []
        for weights in weights_list:
            logits = get_logits(X_test,weights,norm_flag)
            probs = tf.nn.softmax(alpha*logits)
            probs_list.append(probs)
        test_probs = tf.reduce_mean(tf.stack(probs_list),axis=0)
        test_acc = get_accuracy(test_probs,y_test).numpy()
        cce = tf.losses.CategoricalCrossentropy(from_logits=False)
        test_negll = cce(y_test,test_probs).numpy()
        print ("Num_lab = "+str(num_lab)+" Test accuracy = "+str(test_acc))
        acc[ctr][trial] = test_acc
        negll[ctr][trial] = test_negll
        num_lab += num_acq
        ctr += 1
print (np.mean(acc,axis=1))
print (np.mean(negll,axis=1))
acc_filename = 'Results/acc_blr.npy'
np.save(acc_filename,acc)
negll_filename = 'Results/negll_blr.npy'
np.save(negll_filename,negll)
print ('Results Saved')