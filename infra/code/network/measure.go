package network

import (
	"fmt"
	"time"

	"github.com/vishvananda/netns"
)

/* ====================== Node Measure ======================= */

/*
 * Measure influence of nodes' existense on link building speed.
 *
 * Method: Prepare p nodes in advance, and record time to build
 * Q links N(p). Then, 1/Q of the slope of linear function
 * N(p) is our target.
 *
 *   We need to get some sample points and run linear regression
 * to get N(p), Suppose we sample S points in interval [0, P],
 * the whole profiling is as:
 *
 * build_samples = []
 * clean_samples = []
 * Prepare 2 big nodes
 * sampleStep = (P // (S-1))
 * for i in [0, 1, ..., S)
 *   if i > 0
 *     Prepare sampleStep nodes
 *   Create a new backbone namespace B
 *   Create Q links connecting the two big nodes within B
 *   Record build time of the Q links T_build
 *   build_samples.append((i*sampleStep, T_build))
 *   Clean the Q links in B
 *   Record clean time of the Q links T_build
 *   clean_samples.append((i*sampleStep, T_clean))
 * Run linear regression with build_samples and clean_samples,
 *   getting N_build(p) and N_clean(p)
 * Return 1/Q of the slope N(p).
 */
func NodeMeasure(
	lm LinkManager, nm NodeManager,
	sampleNum int, maxSample int, linkNum int) error {
	var err error
	var startTime time.Time
	var origNs netns.NsHandle

	nm.Init()
	lm.Init(nm)

	fmt.Printf("Running node-measure\n")
	fmt.Printf("sampleNum (S): %d\n", sampleNum)
	fmt.Printf("maxSample (P): %d\n", maxSample)
	fmt.Printf("linkNum (Q): %d\n\n", linkNum)
	origNs, err = netns.Get()
	if err != nil {
		return err
	}

	/* Prepare 2 big nodes and a bbns*/
	fmt.Printf("Preparing 2 big nodes...\n")
	for j := 0; j < 2; j += 1 {
		err = nm.SetupNode(j)
		if err != nil {
			return err
		}
	}
	_, err = lm.SetupBbNs()
	if err != nil {
		return err
	}

	/* Sample link setup speed with P existing nodes */
	p := 0
	sampleStep := int(maxSample / (sampleNum - 1))
	for i := 0; i < sampleNum; i += 1 {
		fmt.Printf("Sample (p=%d) starts\n", p)

		/* Prepare p nodes for test i if needed */
		if i > 0 {
			fmt.Printf("Preparing %d nodes...\n", sampleStep)
			for j := 0; j < sampleStep; j += 1 {
				err = nm.SetupNode(p + j + 2)
				if err != nil {
					return err
				}
			}
			fmt.Printf("Synchonizing...\n")
			time.Sleep(20 * time.Second)
			p += sampleStep
		}

		/* Sample i (build stage) */
		fmt.Printf("Sample (p=%d): Building %d links...\n", p, linkNum)
		_, err = lm.EnterBbNs(0)
		if err != nil {
			return err
		}
		startTime = time.Now()
		for j := 0; j < linkNum; j += 1 {
			err = lm.SetupLink(0, 1, -1, -1, 1)
			if err != nil {
				return err
			}
		}
		if err != nil {
			return err
		}
		fmt.Printf("Sample (p=%d) build done, time: %.2fs\n", p, time.Since(startTime).Seconds())
		fmt.Printf("Synchonizing...\n")
		time.Sleep(20 * time.Second)

		/* Sample i (clean stage) */
		fmt.Printf("Sample (p=%d): Cleaning %d links...\n", p, linkNum)
		netns.Set(origNs)
		startTime = time.Now()
		lm.CleanAllLinks(1)
		syncNtlk(0)
		fmt.Printf("Sample (p=%d) clean done, time: %.2fs\n",
			p, time.Since(startTime).Seconds())

		fmt.Printf("Sample (p=%d) ends\n\n", p)
		fmt.Printf("Synchonizing...\n")
		time.Sleep(20 * time.Second)
	}

	/* Clean nodes and the bbns */
	fmt.Printf("End: Cleaning bbns...\n")
	lm.CleanAllBbNs()
	syncNtlk(0)
	fmt.Printf("End: Cleaning %d nodes...\n", p+2)
	for j := 2; j < p+2; j += 1 {
		err = nm.CleanNode(j)
		if err != nil {
			return err
		}
	}
	fmt.Printf("End: Cleaning done\n")

	lm.Delete()
	nm.Delete()

	return nil
}

/* ====================== Link Measure ======================= */

/*
 * Measure influence of links' existense on link building speed.
 *
 * Method: Prepare p links in advance, and record time to build
 * Q links L(p). Then, 1/Q of the slope of linear function
 * L(p) is our target.
 *
 *   We need to get some sample points and run linear regression
 * to get L(p), Suppose we sample S points in interval [0, P],
 * the whole profiling is as:
 *
 * build_samples = []
 * clean_samples = []
 * Prepare S pairs of big nodes
 * Create a backbone namespace B
 * Q = P // (S-1)
 * for i in [0, 1, ..., S)
 *   Create Q links within B to connect a pair of two big nodes
 *   Record build time of last Q links, denoted by T_build
 *   build_samples.append((i*Q, T_build))
 * for i in [0, 1, ..., S)
 *   Clean Q links within B to connect a pair of two big nodes
 *   Record clean time of last Q links, denoted by T_clean
 *   clean_samples.append((i*Q, T_clean))
 * Run linear regression with build_samples and clean_samples,
 *   getting L_build(p) and L_clean(p)
 * Return 1/Q of the slope L(p).
 */
func LinkMeasure(
	lm LinkManager, nm NodeManager,
	sampleNum int, maxSample int) error {
	var err error
	var startTime time.Time
	var origNs netns.NsHandle

	nm.Init()
	lm.Init(nm)

	sampleStep := int(maxSample / (sampleNum - 1))
	fmt.Printf("Running link-measure\n")
	fmt.Printf("sampleNum (S): %d\n", sampleNum)
	fmt.Printf("maxSample (P): %d\n", maxSample)
	fmt.Printf("sampleStep (Q): %d\n\n", sampleStep)
	origNs, err = netns.Get()
	if err != nil {
		return err
	}

	/* Prepare big nodes */
	bigNodeNum := 2 * sampleNum
	fmt.Printf("Preparing %d big nodes...\n", bigNodeNum)
	for i := 0; i < bigNodeNum; i += 1 {
		err = nm.SetupNode(i)
		if err != nil {
			return err
		}
	}

	/* Prepare the backbone namespace */
	_, err = lm.SetupBbNs()
	if err != nil {
		return err
	}
	_, err = lm.EnterBbNs(0)
	if err != nil {
		return err
	}

	fmt.Printf("Synchonizing...\n")
	time.Sleep(5 * time.Second)

	/* Sample for building */
	p := 0
	for i := 0; i < sampleNum; i += 1 {
		/* Build links */
		fmt.Printf("Sample (p=%d): Building %d links...\n", p, sampleStep)
		startTime = time.Now()
		for j := 0; j < sampleStep; j += 1 {
			err = lm.SetupLink(i*2, i*2+1, -1, -1, i+1)
			if err != nil {
				return err
			}
		}
		fmt.Printf("Sample (p=%d) build done, time: %.2fs\n",
			p, time.Since(startTime).Seconds())
		fmt.Printf("Synchonizing...\n")
		time.Sleep(30 * time.Second)
		p += sampleStep
	}

	/* Sample for cleaning */
	p = 0
	for i := 0; i < sampleNum; i += 1 {
		/* Clean links */
		fmt.Printf("Sample (p=%d): Cleaning %d links...\n", p, sampleStep)
		startTime = time.Now()
		lm.CleanAllLinks(i + 1)
		fmt.Printf("Sample (p=%d) clean done, time: %.2fs\n",
			p, time.Since(startTime).Seconds())
		fmt.Printf("Synchonizing...\n")
		time.Sleep(30 * time.Second)
		p += sampleStep
	}

	/* Clean the backbone namespace */
	netns.Set(origNs)
	fmt.Printf("End: Cleaning bbns...\n")
	startTime = time.Now()
	lm.CleanAllBbNs()
	syncNtlk(0)
	fmt.Printf("End: Cleaning done, time: %.2fs\n\n", time.Since(startTime).Seconds())

	/* Clean big nodes */
	startTime = time.Now()
	fmt.Printf("End: Cleaning %d big nodes...\n", bigNodeNum)
	for j := 0; j < bigNodeNum; j += 1 {
		err = nm.CleanNode(j)
		if err != nil {
			return err
		}
	}
	syncNtlk(0)
	fmt.Printf("End: Cleaning done, time: %.2fs\n\n", time.Since(startTime).Seconds())

	lm.Delete()
	nm.Delete()

	return nil
}

/* ====================== Const Measure ======================= */

// Measure influence of constant factors on link building speed.
func ConstMeasure(
	lm LinkManager, nm NodeManager,
	sampleNum int) error {

	var err error
	var origNs netns.NsHandle

	nm.Init()
	lm.Init(nm)

	fmt.Printf("Running const-measure\n")
	fmt.Printf("sampleNum (S): %d\n", sampleNum)
	origNs, _ = netns.Get()

	/* Prepare two virtual nodes */
	fmt.Printf("Preparing 2 virtual nodes...\n")
	for i := 0; i < 2; i += 1 {
		err = nm.SetupNode(i)
		if err != nil {
			return err
		}
	}

	/* Prepare the backbone namespace */
	_, err = lm.SetupBbNs()
	if err != nil {
		return err
	}
	_, err = lm.EnterBbNs(0)
	if err != nil {
		return err
	}

	/*
	 * Build a vlink between the two virtual nodes, and then clean it.
	 * Measure the time taken to build it.
	 * Repeat this process sampleNum times to get an average time.
	 */
	samples := make([]float64, sampleNum)
	sampleNumPerReport := sampleNum / 10
	if sampleNumPerReport == 0 {
		sampleNumPerReport = 1
	}
	for i := 0; i < sampleNum; i += 1 {
		if i%sampleNumPerReport == 0 {
			fmt.Printf("Sample %d: Building a link...\n", i+1)
		}
		startTime := time.Now()
		err = lm.SetupLink(0, 1, -1, -1, 1)
		if err != nil {
			return err
		}
		setupTime := time.Since(startTime).Seconds()
		samples[i] = setupTime
		err = lm.CleanAllLinks(1)
		if err != nil {
			return err
		}
	}
	/* Print average setupTime and the variance of samples */
	avgSetupTime := 0.0
	for _, sample := range samples {
		avgSetupTime += sample
	}
	avgSetupTime /= float64(sampleNum)
	variance := 0.0
	for _, sample := range samples {
		variance += (sample - avgSetupTime) * (sample - avgSetupTime)
	}
	variance /= float64(sampleNum)
	fmt.Printf("Samples: %v\n", samples)
	fmt.Printf("Average setup time: %.4fs\n", avgSetupTime)
	fmt.Printf("Variance of samples: %.4fs\n", variance)

	/* Clean the backbone namespace */
	netns.Set(origNs)
	fmt.Printf("End: Cleaning bbns...\n")
	lm.CleanAllBbNs()
	syncNtlk(0)

	/* Clean the two virtual nodes */
	fmt.Printf("End: Cleaning %d virtual nodes...\n", 2)
	for j := 0; j < 2; j += 1 {
		err = nm.CleanNode(j)
		if err != nil {
			return err
		}
	}

	syncNtlk(0)

	lm.Delete()
	nm.Delete()

	return nil
}
