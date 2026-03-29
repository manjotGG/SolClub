import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { clusterApiUrl, Connection, Keypair, PublicKey } from '@solana/web3.js';
import { Metaplex, keypairIdentity } from '@metaplex-foundation/js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const KEYPAIR_PATH = path.join(__dirname, '../data/nft_minter_keypair.json');

function loadKeypairFromFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const secretKey = JSON.parse(raw);

  if (!Array.isArray(secretKey) || secretKey.length === 0) {
    throw new Error('Invalid keypair file format: expected non-empty array');
  }

  return Keypair.fromSecretKey(Uint8Array.from(secretKey));
}

export async function mintNftToWallet(recipientWalletAddress) {
  try {
    console.log('Minting NFT...');

    if (!recipientWalletAddress) {
      throw new Error('recipientWalletAddress argument is required');
    }

    const recipientPublicKey = new PublicKey(recipientWalletAddress);
    const walletKeypair = loadKeypairFromFile(KEYPAIR_PATH);

    console.log('Minter wallet:', walletKeypair.publicKey.toString());
    console.log('Recipient wallet:', recipientPublicKey.toString());

    const connection = new Connection(clusterApiUrl('devnet'), 'confirmed');
    const metaplex = Metaplex.make(connection).use(keypairIdentity(walletKeypair));

    const { nft } = await metaplex.nfts().create({
      uri: 'https://arweave.net/123',
      name: 'SolClub NFT',
      sellerFeeBasisPoints: 0,
      tokenOwner: recipientPublicKey,
    });

    console.log('Mint address:', nft.address.toString());
    console.log('NFT Minted successfully');

    return nft;
  } catch (error) {
    console.error('Minting failed:', error);
    throw error;
  }
}

const recipientArg = process.argv[2];

(async () => {
  console.log('FILE STARTED');
  if (!recipientArg) {
    console.log('No recipient public key passed. To test call `node mint.js <recipientPublicKey>`.');
    return;
  }

  try {
    await mintNftToWallet(recipientArg);
  } catch (error) {
    console.error('Error in IIFE execution:', error);
    process.exitCode = 1;
  }
})();


