.subckt DUT vp vn vout vdd vss ibias
m5 ibias ibias vss vss nmos l=m5_l w=m5_w m=1 nf=1
m4 net2 ibias vss vss nmos l=m4_l w=m4_w m=1 nf=1
m2 vout vn net2 net2 nmos l=m2_l w=m2_w m=1 nf=1
m0 net3 vp net2 net2 nmos l=m0_l w=m0_w m=1 nf=1
m3 vout net3 vdd vdd pmos l=m3_l w=m3_w m=1 nf=1
m1 net3 net3 vdd vdd pmos l=m1_l w=m1_w m=1 nf=1
.ends DUT
