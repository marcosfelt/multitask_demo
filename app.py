import streamlit as st
import botorch
from gpytorch.mlls.exact_marginal_log_likelihood import ExactMarginalLogLikelihood
import torch
import matplotlib.pyplot as plt
import numpy as np
import io

# Title
st.title("Multitask GP Model")

"""
This is a demo of multitask Gaussian processes, which are a key component of [multitask Bayesian optimization](https://en.wikipedia.org/wiki/Multitask_optimization). The sliders below control the data used to train the single task and multitask models.
"""

# Sliders
period = st.slider(
    "Function Period",
    min_value=2.0,
    max_value=10.0,
    value=5.0,
    step=0.5,
)
n_main = st.slider("Main Task Observations", min_value=0, max_value=50, value=20)
n_aux = st.slider("Auxiliary Task Observations", min_value=0, max_value=50, value=20)

noise = st.slider(
    "Observation Noise", min_value=0.0, max_value=1.0, value=0.1, step=0.1
)
# use_fixed_noise = st.checkbox("Use Fixed Noise Model", False)

# Random number generator
gen = torch.Generator()
gen.manual_seed(100)

f_main = lambda X: 1.5 * torch.cos(period * X[:, 0]) ** 2 + 5 * (X[:, 0]) ** 2
f_aux = lambda X: torch.cos(5 * X[:, 0]) ** 2 + 3 * (X[:, 0] - 0.2) ** 2
gen_inputs = lambda n: torch.atleast_2d(
    torch.linspace(0, 1, n + 1)[:-1] + (1 / n) * torch.rand(n, generator=gen)
).T
gen_obs = lambda X, f, noise: f(X) + noise * torch.normal(
    mean=torch.zeros(X.shape[0]), std=torch.ones(X.shape[0]), generator=gen
)

### Data Generation
X_aux, X_main = gen_inputs(n_aux), gen_inputs(n_main)
i1, i2 = torch.zeros(n_aux, 1), torch.ones(n_main, 1)

train_X = torch.cat([torch.cat([X_aux, i1], -1), torch.cat([X_main, i2], -1)])


train_Y_f_main = gen_obs(X_main, f_main, noise)
train_Y_f_aux = gen_obs(X_aux, f_aux, noise)
train_Y_f_main_mean = train_Y_f_main.mean()
train_Y_f_main_std = train_Y_f_main.std()
train_Y_f_main_norm = (train_Y_f_main - train_Y_f_main_mean) / train_Y_f_main_std
train_Y = torch.cat([train_Y_f_aux, train_Y_f_main]).unsqueeze(-1)
train_Y_mean = train_Y.mean()
train_Y_std = train_Y.std()
train_Y_norm = (train_Y - train_Y_mean) / train_Y_std
train_Yvar = noise * torch.rand(train_X.shape[0], 1)

### Model Training
# if not use_fixed_noise:
model_st = botorch.models.SingleTaskGP(X_main, torch.atleast_2d(train_Y_f_main_norm).T)
model_mt = botorch.models.MultiTaskGP(train_X, train_Y_norm, task_feature=-1)
# else:
#     model_mt = botorch.models.FixedNoiseMultiTaskGP(
#         train_X, train_Y_norm, train_Yvar, task_feature=-1
#     )
mll_st = ExactMarginalLogLikelihood(model_st.likelihood, model_st)
mll_mt = ExactMarginalLogLikelihood(model_mt.likelihood, model_mt)
botorch.fit.fit_gpytorch_model(mll_st)
botorch.fit.fit_gpytorch_model(mll_mt)

### Plotting
st.markdown(
    "Red is for Auxiliary Task, and blue is for Main Task. Dotted lines are the ground truth. Dots are training observations, and translucent lines are posterior samples of the trained model for each task."
)

fig, axes = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
fig.subplots_adjust(wspace=0.3)


# Ground truth
X_plot = np.atleast_2d(np.linspace(0, 1, 100)).T
X_plot = torch.tensor(X_plot).float()
axes[0].plot(X_plot, f_main(X_plot), "--", label="Main Task", alpha=1, c="b")
axes[1].plot(X_plot, f_aux(X_plot), "--", label="Auxiliary Task", alpha=1, c="r")
axes[1].plot(X_plot, f_main(X_plot), "--", label="Main Task", alpha=1, c="b")


# Observations
marker_size = 50
axes[0].scatter(X_main, train_Y_f_main, c="b", s=marker_size)
axes[1].scatter(X_aux, train_Y_f_aux, c="r", s=marker_size)
axes[1].scatter(X_main, train_Y_f_main, c="b", s=marker_size)


# Posterior of model
alpha = 0.05

with torch.no_grad():
    posterior_st = model_st.posterior(X_plot)
    posterior_mt = model_mt.posterior(X_plot)
    for i in range(100):
        y = posterior_st.sample()[0, :, 0] * train_Y_f_main_std + train_Y_f_main_mean
        axes[0].plot(X_plot, y, alpha=alpha, color="b")
    # Auxiliary Task
    for i in range(100):
        y = posterior_mt.sample()[0, :, 0] * train_Y_std + train_Y_mean
        axes[1].plot(X_plot, y, alpha=alpha, color="r")
    # Main Task
    for i in range(100):
        y = posterior_mt.sample()[0, :, 1] * train_Y_std + train_Y_mean
        axes[1].plot(X_plot, y, alpha=alpha, color="b")


# Plot formatting
axes[0].legend(loc="best")
axes[0].set_title("Single-Task")
axes[0].tick_params(direction="in")
axes[1].legend(loc="best")
axes[1].set_title("Multitask")
axes[1].tick_params(direction="in")
axes[0].set_xlabel("x")
axes[1].set_xlabel("x")
fig.supylabel("y")
axes[0].set_xlim(0, 1)
axes[1].set_xlim(0, 1)
st.write(fig)

fn = "st_vs_mt.png"
img = io.BytesIO()
fig.savefig(img, format="png", dpi=300)

btn = st.download_button(
    label="Download image", data=img, file_name=fn, mime="image/png"
)
