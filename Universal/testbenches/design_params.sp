*******************************************************
* design_params.sp -- Global Circuit Parameters
*******************************************************

* --- Power Supplies ---
.param VDD = 1.0
.param VSS = 0.0

* --- Biasing ---
* This is your reference tail current. 
* Ensure this matches your dut.sp biasing requirements.
.param IBIAS = 5u
.param DUT_HAS_VB2 = 0
* --- Loading ---
* Standard load for area/speed trade-offs
.param CL = 500f
.param c0 = 0.2p
.param r0 = 10k
* --- Leakage/Safety ---
* High resistance to prevent floating nodes during DC convergence
.param RLEAK = 100Meg

* --- Timing Constants ---
* Default UGF used as a fallback if the AC sim hasn't run yet
.param UGF_DEFAULT = 50Meg

*******************************************************
* Optimization/Simulator Options
*******************************************************
.option post=2      $ Enables waveform viewing (RTA/Custom WaveView)
.option nomod       $ Clean up the .lis file by hiding model parameters
.option probe       $ Only save signals explicitly requested in .probe
.option runlvl=5

*******************************************************
* Device parameters
*******************************************************
.param m0_l=180n
.param m0_w=1u
.param m1_l=180n
.param m1_w=1u
.param m2_l=180n
.param m2_w=1u
.param m3_l=180n
.param m3_w=1u
.param m4_l=180n
.param m4_w=1u
.param m5_l=180n
.param m5_w=1u
