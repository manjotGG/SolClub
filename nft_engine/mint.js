import fs from 'fs';
import path from 'path';
import { clusterApiUrl, Keypair, Connection } from '@solana/web3.js';
import { Metaplex, keypairIdentity } from '@metaplex-foundation/js';

async function mintNft() {
  try {
    console.log('🚀 Minting NFT...');

    const keypairPath = path.resolve(new URL('../data/nft_minter_keypair.json', import.meta.url));
    const raw = fs.readFileSync(keypairPath, 'utf8');
    const keypairArray = JSON.parse(raw);
    const walletKeypair = Keypair.fromSecretKey(Uint8Array.from(keypairArray));

    const connection = new Connection(clusterApiUrl('devnet'));
    const metaplex = Metaplex.make(connection).use(keypairIdentity(walletKeypair));

    const { nft } = await metaplex.nfts().create({
      uri: 'https://arweave.net/123',
      name: 'SolClub NFT',
      sellerFeeBasisPoints: 0,
    });

    console.log('✅ NFT Minted!');
    console.log('Mint address:', nft.address.toString());
  } catch (error) {
    console.error('❌ Minting failed:', error);
    process.exitCode = 1;
  }
}

mintNft();
