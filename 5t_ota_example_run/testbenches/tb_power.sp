*******************************************************
* tb_power.sp -- OTA Power Consumption Testbench
*******************************************************
.option post=2
.option nomod
.option measform=3
.option results
.temp 27

* --- Formatting for Python parsing ---
.option ingold=2
.option numdgt=10
.option width=5000

**************** Universal DUT Interface **************
.param DUT_HAS_VB2 = 0
.param VB2_DC = 600m

**************** Parameters ***************************
.param VCM=7.021553e-01
.param dummy_var=0

.include "design_params.sp"

**************** Supplies & Inputs ********************
VSS  vss 0 0
VDD1 vdd 0 VDD

* External ideal bias current source
* This current is drawn from VDD and injected into the bias diode/current mirror branch.
IBIAS_SRC vdd ibias DC IBIAS

VVB2 vb2 0 DC 'VB2_DC'

* DC common-mode input for quiescent power
VINP vp 0 DC VCM
VINN vn 0 DC VCM

**************** DUT ***************************
.include "dut_wrapper.sp"

* Pin Order: In+, In-, Out, VDD, VSS, Bias, Vbias2
XU1 vp vn vout vdd vss ibias vb2 DUT_UNIVERSAL

CLOAD vout vss CL

**************** Analysis *****************************
* Dummy DC sweep to force measurement output
.dc dummy_var 0 0 1

**************** Power Measurements *******************
* HSPICE sign convention:
* If the circuit draws current from VDD, I(VDD1) is usually negative.
* Therefore total supply current drawn from VDD is -I(VDD1).

.meas dc IDD_TOTAL_A  FIND par('-I(VDD1)') AT=0
.meas dc IDD_TOTAL_UA PARAM='IDD_TOTAL_A*1e6'

* Total power from VDD, including the ideal IBIAS_SRC branch
.meas dc P_TOTAL_W   PARAM='VDD*IDD_TOTAL_A'
.meas dc P_TOTAL_UW  PARAM='P_TOTAL_W*1e6'

* If you want to exclude the externally supplied bias current source:
* This assumes IBIAS_SRC is an external ideal bias generator, not counted as OTA core power.
.meas dc IDD_CORE_A  PARAM='IDD_TOTAL_A-IBIAS'
.meas dc IDD_CORE_UA PARAM='IDD_CORE_A*1e6'

.meas dc P_CORE_W    PARAM='VDD*IDD_CORE_A'
.meas dc P_CORE_UW   PARAM='P_CORE_W*1e6'

**************** Optional Debug Prints ****************
.print dc V(vdd) V(vout) I(VDD1) I(IBIAS_SRC)

.end
