"""Write an affine registration (pixel -> metres) in the form classify.py reads (metres -> pixel, quadratic terms zero).
Used for the Mie sheet, whose affine fit is not refined further.
usage: affpoly.py <affine.npy> <out.npz>"""
import sys, numpy as np
f = np.load(sys.argv[1]); A = np.array([[f[0], f[1]], [f[3], f[4]]]); t = np.array([f[2], f[5]]); Ai = np.linalg.inv(A)
c0 = np.array([0.0, 0.0]); sc = 2000.0
th = np.r_[-Ai[0] @ t, Ai[0, 0] * sc, Ai[0, 1] * sc, 0, 0, 0, -Ai[1] @ t, Ai[1, 0] * sc, Ai[1, 1] * sc, 0, 0, 0]
np.savez(sys.argv[2], th=th, c0=c0, sc=sc)
