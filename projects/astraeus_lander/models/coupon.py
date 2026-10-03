def build(p,d,s,part):
    r=d['R'];w=d['wall'];c=d['fit'];sp=r-w-c
    # Two test rings are parked behind the display assembly, not part of the rocket.
    male=s.lathe('male_collar_coupon',[(r,0),(r,3),(sp,3),(sp,9),(sp-2,9),(sp-2,0)],center=(100,0));s.finish(male,'accent',bodies=2)
    female=s.lathe('female_bore_coupon',[(r,0),(r,9),(r-w,9),(r-w,0)],center=(100,65));s.finish(female,'accent',bodies=2)
